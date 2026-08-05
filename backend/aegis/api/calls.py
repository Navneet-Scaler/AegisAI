"""Read the call log, export it, and record human decisions.

Reading is public so the dashboard is viewable without a token. Deciding is
not: `/calls/{id}/decide` is the one endpoint that can turn a held,
potentially destructive call into an executed one, and it requires the
bearer token from the moment it exists.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from aegis.aegisai import approvals
from aegis.aegisai.model_store import get_model, save_model
from aegis.auth import require_demo_token
from aegis.db import get_session
from aegis.models import CallStatus, ToolCall, Verdict

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("", response_model=list[ToolCall])
async def list_calls(session: AsyncSession = Depends(get_session)) -> list[ToolCall]:
    result = await session.execute(select(ToolCall).order_by(ToolCall.created_at.desc()))
    return list(result.scalars().all())


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: str) -> str:
    """Excel and Sheets treat a leading =, +, -, @, tab, or carriage return
    as the start of a formula, evaluated the moment the file is opened. The
    fields this guards (agent name, tool arguments, judge reasoning, failure
    reason) can all contain attacker-influenced text, an injected ticket
    body echoed back into judge_reasoning being the exact scenario this
    export exists to make auditable. A leading apostrophe forces spreadsheet
    software to treat the cell as literal text, the standard mitigation."""
    if value and value[0] in _FORMULA_PREFIXES:
        return f"'{value}"
    return value


_EXPORT_COLUMNS = [
    "call_id",
    "created_at",
    "decided_at",
    "agent_name",
    "api_key_id",
    "policy_id",
    "tool_name",
    "arguments",
    "verdict",
    "composite_score",
    "rule_score",
    "pattern_score",
    "judge_score",
    "matched_rules",
    "judge_reasoning",
    "decided_by",
    "executed",
    "failure_reason",
]


@router.get(
    "/export.csv",
    summary="Export the audit trail as CSV",
    description=(
        "Who, what, when, the decision, and the reasoning behind it, one row per call, "
        "timestamped and never mutated after the fact. The shape SOC 2 or ISO 27001 audit "
        "evidence typically expects. Filterable the same way the live feed is; public, "
        "the same as the rest of the read surface, since it has no side effects."
    ),
)
async def export_calls_csv(
    session: AsyncSession = Depends(get_session),
    agent_name: str | None = Query(default=None),
    api_key_id: str | None = Query(default=None),
    verdict: Verdict | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    since: datetime | None = Query(default=None, description="ISO 8601, inclusive."),
    until: datetime | None = Query(default=None, description="ISO 8601, exclusive."),
) -> StreamingResponse:
    query = select(ToolCall).order_by(ToolCall.created_at.desc())
    if agent_name is not None:
        query = query.where(ToolCall.agent_name == agent_name)
    if api_key_id is not None:
        query = query.where(ToolCall.api_key_id == api_key_id)
    if verdict is not None:
        query = query.where(ToolCall.verdict == verdict)
    if tool_name is not None:
        query = query.where(ToolCall.tool_name == tool_name)
    if since is not None:
        query = query.where(ToolCall.created_at >= since)
    if until is not None:
        query = query.where(ToolCall.created_at < until)

    rows = (await session.execute(query)).scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_EXPORT_COLUMNS)
    for row in rows:
        writer.writerow(
            [
                row.id,
                row.created_at.isoformat(),
                row.decided_at.isoformat() if row.decided_at else "",
                _csv_safe(row.agent_name),
                row.api_key_id or "",
                row.policy_id,
                row.tool_name,
                _csv_safe(str(row.arguments)),
                row.verdict.value,
                row.composite_score if row.composite_score is not None else "",
                row.rule_score if row.rule_score is not None else "",
                row.pattern_score if row.pattern_score is not None else "",
                row.judge_score if row.judge_score is not None else "",
                ";".join(row.matched_rules),
                _csv_safe(row.judge_reasoning or ""),
                row.decided_by or "",
                row.executed,
                _csv_safe(row.failure_reason or ""),
            ]
        )

    buffer.seek(0)
    filename = f"aegisai-audit-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{call_id}", response_model=ToolCall)
async def get_call(call_id: str, session: AsyncSession = Depends(get_session)) -> ToolCall:
    call = await session.get(ToolCall, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found.")
    return call


class DecisionRequest(BaseModel):
    approve: bool
    decided_by: str = "reviewer"


@router.post(
    "/{call_id}/decide",
    response_model=ToolCall,
    dependencies=[Depends(require_demo_token)],
)
async def decide_call(
    call_id: str, payload: DecisionRequest, session: AsyncSession = Depends(get_session)
) -> ToolCall:
    # A single UPDATE with status == PENDING in its WHERE clause, rather than
    # a session.get() read followed by a later write, closes the race where
    # two concurrent decisions on the same call both pass a status check
    # before either commits. The database, not this coroutine, is what
    # decides whether a row is still pending, and it decides atomically:
    # only one concurrent request can ever match the WHERE clause and update
    # the row. Without this, two contradictory decisions could both reach
    # the online learner below, training it on the same feature vector with
    # opposite labels.
    result = await session.execute(
        sa_update(ToolCall)
        .where(ToolCall.id == call_id, ToolCall.status == CallStatus.PENDING)
        .values(
            verdict=Verdict.ALLOW if payload.approve else Verdict.BLOCK,
            status=CallStatus.RESOLVED,
            decided_by=payload.decided_by,
            decided_at=datetime.now(UTC),
        )
    )
    await session.commit()

    if result.rowcount == 0:
        existing = await session.get(ToolCall, call_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Call not found.")
        raise HTTPException(status_code=409, detail="Call has already been resolved.")

    call = await session.get(ToolCall, call_id)
    assert call is not None

    # Wakes the coroutine in AegisAI.guard that is polling this row, if this
    # process is the one running it. If it is a different process, the
    # polling loop still finds the resolved row on its own within one
    # interval, so correctness never depends on this firing.
    approvals.signal_decision(call_id)

    # Online learning: a human decision updates the pattern model
    # immediately, on the exact feature vector AegisAI scored at the time,
    # not a recomputation. Calls that failed before pattern scoring ran
    # never got a feature vector, so there is nothing to learn from here.
    # This decision has already won the atomic update above, so exactly one
    # decision for this call ever reaches the learner.
    if call.pattern_features is not None:
        model = await get_model(session)
        model.learn(call.pattern_features, risky=not payload.approve)
        await save_model(session, model)

    return call
