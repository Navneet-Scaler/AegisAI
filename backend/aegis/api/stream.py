"""GET /stream: server sent events, derived from database state.

Polls the `ToolCall` table for rows created or updated since the last tick
and pushes them to the client. There is no separate in-memory feed to keep in
sync with the database, so a call the dashboard sees is guaranteed to be a
call that actually exists in the audit trail.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

from aegis.db import get_sessionmaker
from aegis.models import ToolCall

router = APIRouter(tags=["stream"])

_POLL_INTERVAL_SECONDS = 1.0


@router.get("/stream")
async def stream(request: Request) -> EventSourceResponse:
    async def event_generator():
        sessionmaker = get_sessionmaker()
        seen: dict[str, str] = {}

        while True:
            if await request.is_disconnected():
                break

            async with sessionmaker() as session:  # type: AsyncSession
                result = await session.execute(
                    select(ToolCall).order_by(ToolCall.created_at.desc()).limit(50)
                )
                rows = list(result.scalars().all())

            for row in reversed(rows):
                fingerprint = f"{row.status}:{row.verdict}:{row.executed}"
                if seen.get(row.id) != fingerprint:
                    seen[row.id] = fingerprint
                    yield {
                        "event": "call",
                        "data": json.dumps(
                            {
                                "id": row.id,
                                "tool_name": row.tool_name,
                                "arguments": row.arguments,
                                "verdict": row.verdict.value,
                                "status": row.status.value,
                                "composite_score": row.composite_score,
                                "rule_score": row.rule_score,
                                "pattern_score": row.pattern_score,
                                "judge_score": row.judge_score,
                                "matched_rules": row.matched_rules,
                                "judge_reasoning": row.judge_reasoning,
                                "executed": row.executed,
                            }
                        ),
                    }

            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    return EventSourceResponse(event_generator())
