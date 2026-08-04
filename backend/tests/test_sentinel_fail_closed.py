"""Every layer and dependency fails toward hold, never toward allow. This is
enforced in exactly one place, the try/except in Sentinel.guard, and these
tests inject a failure at each layer independently to prove none of them
finds a path to a silent allow.

Note the distinction the assertions below are careful about: the immediate
result of a failure is `hold`, visible while the call is still pending; if
nobody approves it before the timeout, it then resolves to `block`. Neither
step ever reaches `allow`.
"""

import asyncio
import uuid

import pytest
from sqlmodel import select

from aegis.db import get_sessionmaker
from aegis.models import CallStatus, ToolCall, Verdict
from aegis.sentinel.core import guard


async def test_rules_file_failure_holds_then_times_out_to_block(monkeypatch):
    def broken_load_rules():
        raise ValueError("rules.yaml is corrupt")

    monkeypatch.setattr("aegis.sentinel.core.load_rules", broken_load_rules)

    sessionmaker = get_sessionmaker()

    async def run_guard():
        async with sessionmaker() as session:
            return await guard(
                session=session,
                session_id=str(uuid.uuid4()),
                agent_name="test-agent",
                tool_name="read_ticket",
                arguments={"id": "TCK-4417"},
                step_index=0,
                user_request="read the ticket",
                history=[],
                approval_timeout_seconds=1,
            )

    task = asyncio.create_task(run_guard())
    await asyncio.sleep(0.05)

    async with sessionmaker() as inspect_session:
        rows = (
            (
                await inspect_session.execute(
                    select(ToolCall).where(ToolCall.tool_name == "read_ticket")
                )
            )
            .scalars()
            .all()
        )
        pending = [r for r in rows if r.status == CallStatus.PENDING]
        assert pending, "expected the failed call to be pending, not resolved yet"
        assert pending[0].verdict == Verdict.HOLD
        assert pending[0].failure_reason is not None

    call = await task
    assert call.verdict == Verdict.BLOCK
    assert not call.executed


async def test_pattern_layer_failure_never_reaches_allow(db_session, monkeypatch):
    async def broken_pattern_score(context):
        raise RuntimeError("model file missing")

    monkeypatch.setattr("aegis.sentinel.core.pattern_layer.score", broken_pattern_score)

    call = await guard(
        session=db_session,
        session_id=str(uuid.uuid4()),
        agent_name="test-agent",
        tool_name="read_ticket",
        arguments={"id": "TCK-4417"},
        step_index=0,
        user_request="read the ticket",
        history=[],
        approval_timeout_seconds=1,
    )

    assert call.verdict == Verdict.BLOCK
    assert not call.executed


async def test_judge_layer_failure_never_reaches_allow(db_session, monkeypatch):
    async def broken_judge_score(context, *, user_request, history):
        raise TimeoutError("judge API timed out")

    monkeypatch.setattr("aegis.sentinel.core.judge_layer.score", broken_judge_score)

    call = await guard(
        session=db_session,
        session_id=str(uuid.uuid4()),
        agent_name="test-agent",
        tool_name="read_ticket",
        arguments={"id": "TCK-4417"},
        step_index=0,
        user_request="read the ticket",
        history=[],
        approval_timeout_seconds=1,
    )

    assert call.verdict == Verdict.BLOCK
    assert not call.executed


async def test_unresolved_hold_times_out_to_block_not_allow(db_session):
    call = await guard(
        session=db_session,
        session_id=str(uuid.uuid4()),
        agent_name="test-agent",
        tool_name="delete_customer",
        arguments={"customer_ids": ["CUST-1001"]},
        step_index=0,
        user_request="delete the customer",
        history=[],
        approval_timeout_seconds=1,
    )

    assert call.verdict == Verdict.BLOCK
    assert call.decided_by == "sentinel-timeout"
    assert not call.executed


@pytest.mark.parametrize(
    "tool_name,arguments",
    [
        ("read_ticket", {"id": "TCK-4417"}),
        ("search_customers", {"query": "acme"}),
        ("create_refund", {"customer_id": "CUST-1001", "amount": 10, "reason": "test"}),
    ],
)
async def test_allowed_calls_actually_execute(db_session, tool_name, arguments):
    call = await guard(
        session=db_session,
        session_id=str(uuid.uuid4()),
        agent_name="test-agent",
        tool_name=tool_name,
        arguments=arguments,
        step_index=0,
        user_request="a routine request",
        history=[],
        approval_timeout_seconds=1,
    )

    assert call.verdict == Verdict.ALLOW
    assert call.executed
    assert call.result is not None
