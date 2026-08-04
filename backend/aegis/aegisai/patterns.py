"""The pattern layer: has this agent done anything like this before.

Computes history signals from the call log, extracts a feature vector, and
scores it with the online classifier. Returns the feature vector alongside
the score so the caller can persist it on the `ToolCall` row; the exact
vector used for a decision is what `learn()` trains on later, not a
recomputation that could have drifted by the time a human responds.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.aegisai.features import HistorySignals, extract, shape_key
from aegis.aegisai.model_store import get_model
from aegis.aegisai.rules import CallContext
from aegis.models import CallStatus, ToolCall, Verdict

NEUTRAL_PRIOR_APPROVAL_RATE = 0.5


async def _history_signals(
    session: AsyncSession, *, agent_name: str, tool_name: str, arguments: dict
) -> HistorySignals:
    target_shape = shape_key(tool_name, arguments)

    past_rows = (
        (await session.execute(select(ToolCall.arguments).where(ToolCall.tool_name == tool_name)))
        .scalars()
        .all()
    )
    seen_before = any(shape_key(tool_name, row) == target_shape for row in past_rows)

    resolved = (
        await session.execute(
            select(ToolCall.verdict, func.count())
            .where(
                ToolCall.agent_name == agent_name,
                ToolCall.tool_name == tool_name,
                ToolCall.status == CallStatus.RESOLVED,
            )
            .group_by(ToolCall.verdict)
        )
    ).all()

    total = sum(count for _, count in resolved)
    approved = sum(count for verdict, count in resolved if verdict == Verdict.ALLOW)
    prior_rate = (approved / total) if total > 0 else NEUTRAL_PRIOR_APPROVAL_RATE

    return HistorySignals(shape_seen_before=seen_before, prior_approval_rate=prior_rate)


async def score(
    context: CallContext,
    *,
    session: AsyncSession,
    agent_name: str,
    step_index: int,
) -> tuple[float, list[float]]:
    history = await _history_signals(
        session, agent_name=agent_name, tool_name=context.tool.name, arguments=context.arguments
    )
    features = extract(context, step_index=step_index, history=history)

    model = await get_model(session)
    return model.risk(features), features
