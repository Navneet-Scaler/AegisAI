"""The LLM provider boundary.

Three implementations share this protocol: `gemini.py` calls the live API,
`replay.py` serves recorded responses so the public demo never depends on a
rate limited free tier key, and `mock.py` is fully scripted for tests. The
agent loop and the judge only ever depend on this protocol, never on a
concrete provider, which is what makes swapping between them free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCallRequest:
    """A tool call the model wants to make."""

    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AgentTurn:
    """One step of the ReAct loop: either the model reasoned to a final answer,
    or it proposed exactly one tool call to make next."""

    thought: str
    tool_call: ToolCallRequest | None
    final_answer: str | None = None


@dataclass(frozen=True)
class JudgeVerdict:
    consistent: bool
    risk: float
    reasoning: str


class LLMProvider(Protocol):
    async def next_turn(
        self,
        *,
        user_request: str,
        history: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]],
    ) -> AgentTurn: ...

    async def judge(
        self,
        *,
        user_request: str,
        history: list[dict[str, Any]],
        proposed_call: ToolCallRequest,
    ) -> JudgeVerdict: ...
