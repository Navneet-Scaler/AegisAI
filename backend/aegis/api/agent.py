"""POST /agent/run: drive one ReAct run to completion.

Phase 1 only. No auth here yet: this endpoint executes tools directly with no
risk scoring in front of it, which is exactly why it must not be reachable
from a real deployment. It is superseded once Sentinel exists in Phase 2.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from aegis.agent.factory import get_provider
from aegis.agent.loop import run_agent
from aegis.tools import registry

router = APIRouter(prefix="/agent", tags=["agent"])


class RunRequest(BaseModel):
    request: str


class RunResponse(BaseModel):
    final_answer: str | None
    steps_taken: int
    stopped_reason: str
    history: list[dict]


@router.post("/run", response_model=RunResponse)
async def run(payload: RunRequest) -> RunResponse:
    result = await run_agent(
        user_request=payload.request,
        provider=get_provider(),
        tools=registry,
    )
    return RunResponse(
        final_answer=result.final_answer,
        steps_taken=result.steps_taken,
        stopped_reason=result.stopped_reason,
        history=result.history,
    )
