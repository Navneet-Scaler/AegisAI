"""The ReAct loop.

Phase 1 scope only: this drives the provider and executes tools directly, with
no risk scoring in front of them yet. From Phase 2 onward, `execute` is
replaced by a call through `Sentinel.guard`, and that swap is the entire
point of the project: the loop's shape does not change, only what stands
between it and the tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aegis.agent.provider import AgentTurn, LLMProvider, ToolCallRequest
from aegis.tools.registry import ToolRegistry

MAX_STEPS = 10


@dataclass
class RunResult:
    final_answer: str | None
    history: list[dict[str, Any]] = field(default_factory=list)
    steps_taken: int = 0
    stopped_reason: str = "final_answer"


async def run_agent(
    *,
    user_request: str,
    provider: LLMProvider,
    tools: ToolRegistry,
    max_steps: int = MAX_STEPS,
) -> RunResult:
    history: list[dict[str, Any]] = []

    for _ in range(max_steps):
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
            )

        result = _execute(turn.tool_call, tools)
        history.append(
            {
                "tool_name": turn.tool_call.tool_name,
                "arguments": turn.tool_call.arguments,
                "result": result,
            }
        )

    return RunResult(
        final_answer=None,
        history=history,
        steps_taken=len(history),
        stopped_reason="max_steps",
    )


def _execute(call: ToolCallRequest, tools: ToolRegistry) -> Any:
    tool = tools.require(call.tool_name)
    return tool.fn(**call.arguments)
