"""The ReAct loop.

Every proposed tool call passes through `AegisAI.guard` before it can
execute. There is no other path from here to a tool's implementation: the
loop holds a reference to the tool registry only to list schemas for the
model, never to call a tool directly. That absence is the whole point of the
project, not an implementation detail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from aegis.aegisai.core import guard
from aegis.agent.provider import AgentTurn, LLMProvider
from aegis.models import Verdict
from aegis.tools.registry import ToolRegistry

MAX_STEPS = 10


@dataclass
class RunResult:
    final_answer: str | None
    history: list[dict[str, Any]] = field(default_factory=list)
    steps_taken: int = 0
    stopped_reason: str = "final_answer"
    call_ids: list[str] = field(default_factory=list)


async def run_agent(
    *,
    user_request: str,
    provider: LLMProvider,
    tools: ToolRegistry,
    session: AsyncSession,
    session_id: str,
    agent_name: str = "demo-agent",
    approval_timeout_seconds: int = 120,
    max_steps: int = MAX_STEPS,
) -> RunResult:
    history: list[dict[str, Any]] = []
    call_ids: list[str] = []

    for step_index in range(max_steps):
        turn: AgentTurn = await provider.next_turn(
            user_request=user_request,
            history=history,
            tool_schemas=tools.schemas(),
        )

        if turn.tool_call is None:
            return RunResult(
                final_answer=turn.final_answer,
                history=history,
                steps_taken=len(history),
                stopped_reason="final_answer",
                call_ids=call_ids,
            )

        call = await guard(
            session=session,
            session_id=session_id,
            agent_name=agent_name,
            tool_name=turn.tool_call.tool_name,
            arguments=turn.tool_call.arguments,
            step_index=step_index,
            user_request=user_request,
            history=history,
            approval_timeout_seconds=approval_timeout_seconds,
        )
        call_ids.append(call.id)

        history.append(
            {
                "tool_name": turn.tool_call.tool_name,
                "arguments": turn.tool_call.arguments,
                "result": call.result if call.executed else _refusal_text(call),
                "verdict": call.verdict.value,
            }
        )

    return RunResult(
        final_answer=None,
        history=history,
        steps_taken=len(history),
        stopped_reason="max_steps",
        call_ids=call_ids,
    )


def _refusal_text(call) -> str:
    if call.verdict == Verdict.BLOCK:
        reason = call.judge_reasoning or "blocked by policy"
        return f"[aegisai blocked this call: {reason}]"
    return "[aegisai held this call and it was not approved in time]"
