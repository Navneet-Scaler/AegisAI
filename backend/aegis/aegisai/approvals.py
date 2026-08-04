"""Wait for a held call to be resolved by a human.

Pending state lives in the `ToolCall` row itself, not in an in-process
`asyncio.Event`. This function polls that row. An in-process event is used
only as a fast-path wakeup, never as the source of truth, so a restart mid
approval leaves the row pending and recoverable instead of losing the wait
entirely, and correctness does not depend on how many instances are running.

Timing out counts as a refusal: `block`, not `allow`. A human who never shows
up is not consent.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from aegis.models import CallStatus, ToolCall, Verdict

_POLL_INTERVAL_SECONDS = 0.25

# In-process wakeups, keyed by call id, purely as a latency optimization.
# Never read for correctness, only used to shorten the next poll's wait.
_wakeups: dict[str, asyncio.Event] = {}


def signal_decision(call_id: str) -> None:
    event = _wakeups.get(call_id)
    if event is not None:
        event.set()


async def wait_for_decision(
    *, call_id: str, session: AsyncSession, timeout_seconds: int
) -> Verdict:
    event = _wakeups.setdefault(call_id, asyncio.Event())
    elapsed = 0.0

    try:
        while elapsed < timeout_seconds:
            row = await session.get(ToolCall, call_id)
            if row is not None and row.status == CallStatus.RESOLVED:
                return row.verdict

            try:
                await asyncio.wait_for(event.wait(), timeout=_POLL_INTERVAL_SECONDS)
                event.clear()
            except TimeoutError:
                pass
            elapsed += _POLL_INTERVAL_SECONDS
            session.expire_all()

        return Verdict.BLOCK
    finally:
        _wakeups.pop(call_id, None)


async def find_pending(session: AsyncSession) -> list[ToolCall]:
    result = await session.execute(select(ToolCall).where(ToolCall.status == CallStatus.PENDING))
    return list(result.scalars().all())
