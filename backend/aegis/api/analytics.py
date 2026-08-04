"""Read-only analytics: block rate over time and the pattern model's state.

Public, like the rest of the read surface. There is nothing here a reviewer
could use to bypass a decision, only to see how the system has behaved.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.db import get_session
from aegis.models import ToolCall, Verdict
from aegis.sentinel.features import FEATURE_NAMES
from aegis.sentinel.model_store import get_model

router = APIRouter(prefix="/analytics", tags=["analytics"])


class ModelSnapshot(BaseModel):
    update_count: int
    feature_names: list[str]
    weights: list[float]


@router.get("/model", response_model=ModelSnapshot)
async def model_snapshot(session: AsyncSession = Depends(get_session)) -> ModelSnapshot:
    model = await get_model(session)
    weights = model.to_weights()
    return ModelSnapshot(
        update_count=model.update_count,
        feature_names=FEATURE_NAMES,
        weights=weights["coef"][0],
    )


class VerdictBreakdown(BaseModel):
    verdict: str
    count: int


@router.get("/verdicts", response_model=list[VerdictBreakdown])
async def verdict_breakdown(session: AsyncSession = Depends(get_session)) -> list[VerdictBreakdown]:
    rows = (
        await session.execute(select(ToolCall.verdict, func.count()).group_by(ToolCall.verdict))
    ).all()
    return [VerdictBreakdown(verdict=Verdict(v).value, count=c) for v, c in rows]


class ToolBreakdown(BaseModel):
    tool_name: str
    total: int
    blocked: int
    held: int


@router.get("/tools", response_model=list[ToolBreakdown])
async def tool_breakdown(session: AsyncSession = Depends(get_session)) -> list[ToolBreakdown]:
    # Grouping in Python rather than SQL: summing a boolean comparison reads
    # differently across SQLite and Postgres, and this table is small enough
    # in a demo deployment that the extra round trip cost is not worth the
    # dialect-specific SQL to avoid it.
    rows = (await session.execute(select(ToolCall.tool_name, ToolCall.verdict))).all()

    breakdown: dict[str, ToolBreakdown] = {}
    for tool_name, verdict in rows:
        entry = breakdown.setdefault(
            tool_name, ToolBreakdown(tool_name=tool_name, total=0, blocked=0, held=0)
        )
        entry.total += 1
        if verdict == Verdict.BLOCK:
            entry.blocked += 1
        elif verdict == Verdict.HOLD:
            entry.held += 1

    return list(breakdown.values())
