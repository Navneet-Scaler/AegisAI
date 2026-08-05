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
                row.agent_name,
                row.api_key_id or "",
                row.policy_id,
                row.tool_name,
                str(row.arguments),
                row.verdict.value,
                row.composite_score if row.composite_score is not None else "",
                row.rule_score if row.rule_score is not None else "",
                row.pattern_score if row.pattern_score is not None else "",
                row.judge_score if row.judge_score is not None else "",
                ";".join(row.matched_rules),
                row.judge_reasoning or "",
                row.decided_by or "",
                row.executed,
                row.failure_reason or "",
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
    call = await session.get(ToolCall, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found.")
    if call.status == CallStatus.RESOLVED:
        raise HTTPException(status_code=409, detail="Call has already been resolved.")

    call.verdict = Verdict.ALLOW if payload.approve else Verdict.BLOCK
    call.status = CallStatus.RESOLVED
    call.decided_by = payload.decided_by
    call.decided_at = datetime.now(UTC)

    session.add(call)
    await session.commit()
    await session.refresh(call)

    # Wakes the coroutine in AegisAI.guard that is polling this row, if this
    # process is the one running it. If it is a different process, the
    # polling loop still finds the resolved row on its own within one
    # interval, so correctness never depends on this firing.
    approvals.signal_decision(call_id)

    # Online learning: a human decision updates the pattern model
    # immediately, on the exact feature vector AegisAI scored at the time,
    # not a recomputation. Calls that failed before pattern scoring ran
    # never got a feature vector, so there is nothing to learn from here.
    if call.pattern_features is not None:
        model = await get_model(session)
        model.learn(call.pattern_features, risky=not payload.approve)
        await save_model(session, model)

    return call
