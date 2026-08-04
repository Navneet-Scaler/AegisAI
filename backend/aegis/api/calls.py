"""Read the call log and record human decisions.

Reading is public so the dashboard is viewable without a token. Deciding is
not: `/calls/{id}/decide` is the one endpoint that can turn a held,
potentially destructive call into an executed one, and it requires the
bearer token from the moment it exists.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
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
