"""POST /agent/run: drive one ReAct run to completion through AegisAI.

Every tool call the agent proposes is created and scored inside
`AegisAI.guard`; this endpoint has no path to a tool that bypasses it.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.agent.factory import get_provider
from aegis.agent.loop import run_agent
from aegis.agent.provider import LLMProvider
from aegis.config import Settings, get_settings
from aegis.db import get_session
from aegis.models import AgentSession
from aegis.tools import registry

router = APIRouter(prefix="/agent", tags=["agent"])


class RunRequest(BaseModel):
    request: str
    agent_name: str = "demo-agent"
    # Only meaningful in mock and replay mode, where the agent's own turns
    # come from a fixed, reviewable script rather than a live model reading
    # this field: "refund" (default) always allows, "delete" always holds
    # via the destructive-delete rule, useful for exercising the approval
    # flow through the API without a live provider. Live mode ignores this
    # and lets Gemini decide freely from `request`.
    scenario: str = "refund"


class RunResponse(BaseModel):
    session_id: str
    final_answer: str | None
    steps_taken: int
    stopped_reason: str
    history: list[dict]
    call_ids: list[str]


@router.post("/run", response_model=RunResponse)
async def run(payload: RunRequest, session: AsyncSession = Depends(get_session)) -> RunResponse:
    settings = get_settings()
    session_id = str(uuid4())

    agent_session = AgentSession(
        id=session_id, agent_name=payload.agent_name, user_request=payload.request
    )
    session.add(agent_session)
    await session.commit()

    result = await run_agent(
        user_request=payload.request,
        provider=_provider_for(settings, payload.scenario),
        tools=registry,
        session=session,
        session_id=session_id,
        agent_name=payload.agent_name,
        approval_timeout_seconds=settings.approval_timeout_seconds,
    )
    return RunResponse(
        session_id=session_id,
        final_answer=result.final_answer,
        steps_taken=result.steps_taken,
        stopped_reason=result.stopped_reason,
        history=result.history,
        call_ids=result.call_ids,
    )


def _provider_for(settings: Settings, scenario: str) -> LLMProvider:
    """Live mode always uses the cached singleton and ignores `scenario`,
    since a real model decides its own turns from the request text. Mock and
    replay mode construct a fresh provider per scenario rather than reusing
    the cached one, since the cached singleton (also used by the judge
    layer) is fixed to the default script."""
    if settings.llm_mode == "mock":
        from aegis.agent.mock import SCENARIOS, MockProvider

        return MockProvider(SCENARIOS.get(scenario, SCENARIOS["refund"]))
    if settings.llm_mode == "replay":
        from aegis.agent.replay import ReplayProvider

        return ReplayProvider(scenario=scenario)
    return get_provider()
