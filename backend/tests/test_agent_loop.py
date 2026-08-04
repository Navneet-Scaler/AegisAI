"""Phase 1 behaviour (the agent completes a multi-step task with zero API
keys) plus Phase 2's chokepoint guarantee: every call passes through
Sentinel.guard, which is why these tests now need a database session."""

import uuid

from aegis.agent.loop import run_agent
from aegis.agent.mock import MockProvider
from aegis.tools import registry


async def test_agent_completes_multi_step_refund_task(db_session):
    result = await run_agent(
        user_request="Please refund the duplicate charge on ticket TCK-4417.",
        provider=MockProvider(),
        tools=registry,
        session=db_session,
        session_id=str(uuid.uuid4()),
    )

    assert result.stopped_reason == "final_answer"
    assert result.final_answer is not None
    called = [step["tool_name"] for step in result.history]
    assert called == ["read_ticket", "search_customers", "create_refund"]
    assert len(result.call_ids) == 3


async def test_unknown_tool_call_raises_key_error_captured_as_a_hold(db_session):
    """An unknown tool is not a scoring failure the guard can hide; the
    scoring pipeline raises, and the fail-closed wrapper turns that into a
    hold rather than ever reaching execution."""
    from aegis.agent.provider import AgentTurn, ToolCallRequest

    class BadProvider:
        async def next_turn(self, **kwargs):
            return AgentTurn(thought="", tool_call=ToolCallRequest("delete_the_internet", {}))

        async def judge(self, **kwargs):
            raise NotImplementedError

    result = await run_agent(
        user_request="x",
        provider=BadProvider(),
        tools=registry,
        session=db_session,
        session_id=str(uuid.uuid4()),
        approval_timeout_seconds=1,
        max_steps=1,
    )

    assert result.stopped_reason == "max_steps"
    assert result.history[0]["verdict"] == "block"
