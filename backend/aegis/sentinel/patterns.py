"""The pattern layer.

Phase 2 stub: returns the same "nothing known against it" baseline the rule
layer uses when nothing matches, so the composite score stays meaningful
before this layer has anything to say. Phase 3 replaces `score` with an
online `SGDClassifier` that updates immediately on every human decision.
"""

from __future__ import annotations

from aegis.sentinel.rules import CallContext
from aegis.sentinel.scoring import LAYER_UNAVAILABLE_BASELINE


async def score(context: CallContext) -> float:
    return LAYER_UNAVAILABLE_BASELINE
