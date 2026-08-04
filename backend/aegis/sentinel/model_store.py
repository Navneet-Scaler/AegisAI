"""Load, persist, and cache the pattern model against `ModelState`.

An in-process cache avoids reconstructing and reseeding the classifier on
every single call, but the database row is still the source of truth: if the
row exists, its weights are what gets loaded, and every `learn()` call
writes back to it immediately. `invalidate()` is called by `/demo/reset` so
a reset actually clears the in-memory copy too, not just the row.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from aegis.models import ModelState
from aegis.sentinel.model import PatternModel

_MODEL_ROW_ID = "pattern-model"
_cached: PatternModel | None = None


def invalidate() -> None:
    global _cached
    _cached = None


async def get_model(session: AsyncSession) -> PatternModel:
    global _cached
    if _cached is not None:
        return _cached

    row = await session.get(ModelState, _MODEL_ROW_ID)
    if row is not None:
        _cached = PatternModel.from_weights(row.weights)
    else:
        _cached = PatternModel()

    return _cached


async def save_model(session: AsyncSession, model: PatternModel) -> None:
    row = await session.get(ModelState, _MODEL_ROW_ID)
    if row is None:
        row = ModelState(id=_MODEL_ROW_ID)

    row.weights = model.to_weights()
    row.updated_at = datetime.now(UTC)
    session.add(row)
    await session.commit()
