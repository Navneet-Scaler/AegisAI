"""Phase 1: the agent completes a multi-step task end to end with zero API
keys, using the deterministic mock provider."""

from aegis.agent.loop import run_agent
from aegis.agent.mock import MockProvider
from aegis.tools import registry


async def test_agent_completes_multi_step_refund_task():
    result = await run_agent(
        user_request="Please refund the duplicate charge on ticket TCK-4417.",
        provider=MockProvider(),
        tools=registry,
    )

    assert result.stopped_reason == "final_answer"
    assert result.final_answer is not None
    called = [step["tool_name"] for step in result.history]
    assert called == ["read_ticket", "search_customers", "create_refund"]


async def test_unknown_tool_call_raises_rather_than_silently_skipping():
    from aegis.agent.provider import AgentTurn, ToolCallRequest

    class BadProvider:
        async def next_turn(self, **kwargs):
            return AgentTurn(
                thought="",
                tool_call=ToolCallRequest("delete_the_internet", {}),
            )

        async def judge(self, **kwargs):
            raise NotImplementedError

    import pytest

    with pytest.raises(KeyError):
        await run_agent(user_request="x", provider=BadProvider(), tools=registry)
