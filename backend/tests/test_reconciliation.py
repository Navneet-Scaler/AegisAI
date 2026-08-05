"""`_execute` commits `executed = True` on its own, immediately, separate
from the resolve commit that normally follows it. That gap is deliberately
small, not zero: a crash between those two commits leaves a row that
genuinely ran but was never marked resolved. `reconcile_orphaned_executions`
is what closes that gap at the next startup, on the record rather than
silently.
"""

import uuid

from aegis.aegisai.core import reconcile_orphaned_executions
from aegis.models import CallStatus, ToolCall, Verdict


async def test_reconcile_marks_executed_but_unresolved_calls_resolved(db_session):
    orphan = ToolCall(
        id=str(uuid.uuid4()),
        session_id="orphan-session",
        agent_name="test-agent",
        tool_name="read_ticket",
        arguments={"id": "TCK-4417"},
        step_index=0,
        verdict=Verdict.ALLOW,
        status=CallStatus.PENDING,
        executed=True,
    )
    db_session.add(orphan)
    await db_session.commit()

    reconciled_ids = await reconcile_orphaned_executions(db_session)

    assert orphan.id in reconciled_ids
    await db_session.refresh(orphan)
    assert orphan.status == CallStatus.RESOLVED
    assert orphan.decided_by == "aegisai-reconciled-after-restart"


async def test_reconcile_leaves_normally_resolved_calls_alone(db_session):
    normal = ToolCall(
        id=str(uuid.uuid4()),
        session_id="normal-session",
        agent_name="test-agent",
        tool_name="read_ticket",
        arguments={"id": "TCK-4417"},
        step_index=0,
        verdict=Verdict.ALLOW,
        status=CallStatus.RESOLVED,
        executed=True,
        decided_by="aegisai-auto-allow",
    )
    db_session.add(normal)
    await db_session.commit()

    reconciled_ids = await reconcile_orphaned_executions(db_session)

    assert normal.id not in reconciled_ids


async def test_reconcile_leaves_genuinely_pending_calls_alone(db_session):
    pending = ToolCall(
        id=str(uuid.uuid4()),
        session_id="pending-session",
        agent_name="test-agent",
        tool_name="delete_customer",
        arguments={"customer_ids": ["CUST-1001"]},
        step_index=0,
        verdict=Verdict.HOLD,
        status=CallStatus.PENDING,
        executed=False,
    )
    db_session.add(pending)
    await db_session.commit()

    reconciled_ids = await reconcile_orphaned_executions(db_session)

    assert pending.id not in reconciled_ids
    await db_session.refresh(pending)
    assert pending.status == CallStatus.PENDING
