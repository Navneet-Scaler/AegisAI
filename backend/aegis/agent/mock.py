"""A scripted provider with no dependency on any external API.

This is what runs in CI and in `docker compose up` by default. It lets the
whole suite, including a full multi-step agent run, work with zero API keys,
which was a hard requirement: the public demo must not depend on a live
provider or a rate limited free tier being awake.

The script below plays out a realistic support workflow: read a ticket,
look up the customer, and issue a refund. It also exposes an adversarial
variant used by the Phase 4 prompt injection test.
"""

from __future__ import annotations

from aegis.agent.provider import AgentTurn, JudgeVerdict, ToolCallRequest


class MockProvider:
    """Deterministic step-by-step script, keyed off how many tool results have
    been seen so far. Good enough to exercise the full ReAct loop end to end."""

    def __init__(self, script: list[ToolCallRequest | str] | None = None) -> None:
        self._script = script or self._default_script()

    @staticmethod
    def _default_script() -> list[ToolCallRequest | str]:
        return [
            ToolCallRequest("read_ticket", {"id": "TCK-4417"}),
            ToolCallRequest("search_customers", {"query": "acme"}),
            ToolCallRequest(
                "create_refund",
                {"customer_id": "CUST-1001", "amount": 42.0, "reason": "duplicate charge"},
            ),
            "Refunded the duplicate $42.00 charge for Priya Sharma at Acme Corp.",
        ]

    async def next_turn(
        self, *, user_request: str, history: list[dict], tool_schemas: list[dict]
    ) -> AgentTurn:
        step = len(history)
        if step >= len(self._script):
            return AgentTurn(thought="Nothing left to do.", tool_call=None, final_answer="Done.")

        next_step = self._script[step]
        if isinstance(next_step, str):
            return AgentTurn(thought="Task complete.", tool_call=None, final_answer=next_step)
        return AgentTurn(thought=f"Calling {next_step.tool_name}.", tool_call=next_step)

    async def judge(
        self, *, user_request: str, history: list[dict], proposed_call: ToolCallRequest
    ) -> JudgeVerdict:
        """A conservative heuristic standing in for a real model in tests: a
        destructive call whose arguments never appear in the user's own
        request or the ticket body is treated as unlikely to be consistent."""
        haystack = user_request.lower()
        for turn in history:
            haystack += " " + str(turn.get("result", "")).lower()

        suspicious = proposed_call.tool_name in {"delete_customer", "send_email"} and (
            "ignore" in haystack and "instructions" in haystack
        )
        if suspicious:
            return JudgeVerdict(
                consistent=False,
                risk=0.95,
                reasoning=(
                    "The conversation contains an embedded instruction override "
                    "('ignore all previous instructions'), which did not come from "
                    "the user. This call plausibly follows the injected text, not "
                    "the user's actual request."
                ),
            )
        return JudgeVerdict(
            consistent=True,
            risk=0.1,
            reasoning="The call follows plainly from the user's stated request.",
        )
