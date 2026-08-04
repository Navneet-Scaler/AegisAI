"""Replay provider: serves judge verdicts recorded from real Gemini calls.

This is the default public demo path. Real judge calls rarely repeat an exact
argument shape, so caching by argument hash would rarely hit; replaying a
fixed set of recorded scenarios sidesteps the Gemini free tier rate limit
entirely rather than mitigating it. The agent loop itself uses the same
scripted turns as `MockProvider`, since the interesting demo behaviour lives
in the judge, not in the agent's own reasoning.
"""

from __future__ import annotations

import json
from pathlib import Path

from aegis.agent.mock import MockProvider
from aegis.agent.provider import AgentTurn, JudgeVerdict, ToolCallRequest

_FIXTURES_PATH = Path(__file__).resolve().parent.parent / "seed" / "judge_fixtures.json"


def _load_fixtures() -> dict[str, dict]:
    if not _FIXTURES_PATH.exists():
        return {}
    return json.loads(_FIXTURES_PATH.read_text())


def _fixture_key(proposed_call: ToolCallRequest) -> str:
    return proposed_call.tool_name


class ReplayProvider:
    def __init__(self) -> None:
        self._mock = MockProvider()
        self._fixtures = _load_fixtures()

    async def next_turn(
        self, *, user_request: str, history: list[dict], tool_schemas: list[dict]
    ) -> AgentTurn:
        return await self._mock.next_turn(
            user_request=user_request, history=history, tool_schemas=tool_schemas
        )

    async def judge(
        self, *, user_request: str, history: list[dict], proposed_call: ToolCallRequest
    ) -> JudgeVerdict:
        fixture = self._fixtures.get(_fixture_key(proposed_call))
        if fixture is not None:
            return JudgeVerdict(
                consistent=bool(fixture["consistent"]),
                risk=float(fixture["risk"]),
                reasoning=str(fixture["reasoning"]),
            )
        # No recorded fixture for this tool: fall back to the same
        # conservative heuristic the mock provider uses, rather than
        # inventing a verdict.
        return await self._mock.judge(
            user_request=user_request, history=history, proposed_call=proposed_call
        )
