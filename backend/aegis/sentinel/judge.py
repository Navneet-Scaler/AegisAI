"""The LLM judge layer.

Phase 2 stub: returns the "nothing known against it" baseline. Phase 4
replaces `score` with a real call through the configured `LLMProvider`,
asking whether the proposed call actually follows from the user's request,
with a strict timeout and any failure turning into a `hold`, never a silent
allow.
"""

from __future__ import annotations

from aegis.sentinel.rules import CallContext
from aegis.sentinel.scoring import LAYER_UNAVAILABLE_BASELINE


async def score(
    context: CallContext, *, user_request: str, history: list[dict]
) -> tuple[float, str | None]:
    return LAYER_UNAVAILABLE_BASELINE, None
