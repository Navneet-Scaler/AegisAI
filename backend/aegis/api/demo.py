"""POST /demo/reset: put the public demo back into a clean starting state.

Token protected, same as every other control-plane write. A live public
dashboard gets clicked around by more than one visitor; without this, the
next person inherits stranded pending calls and drifted model weights from
whoever looked at it before them.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete

from aegis.auth import require_demo_token
from aegis.db import get_session
from aegis.models import AgentSession, ModelState, ToolCall
from aegis.sentinel import model_store
from aegis.tools.crm import reset_demo_data

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/reset", dependencies=[Depends(require_demo_token)])
async def reset(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(delete(ToolCall))
    await session.execute(delete(AgentSession))
    await session.execute(delete(ModelState))
    await session.commit()

    reset_demo_data()
    # The database row is gone; the in-process cached model would otherwise
    # keep serving drifted weights until the next restart.
    model_store.invalidate()

    return {"status": "reset"}
