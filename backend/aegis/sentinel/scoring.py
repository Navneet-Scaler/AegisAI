"""The composite score.

Phase 2 ships the rule layer for real. The pattern and judge layers arrive in
Phases 3 and 4; until then their callers in `core.py` supply the same
"nothing known against it" baseline the rule layer uses when nothing matches,
rather than 0 (affirmatively safe) or 1 (maximally suspicious). This keeps the
composite meaningful at every phase instead of only once all three layers
exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from aegis.models import Verdict

RULE_WEIGHT = 0.35
PATTERN_WEIGHT = 0.30
JUDGE_WEIGHT = 0.35

BLOCK_THRESHOLD = 0.75
HOLD_THRESHOLD = 0.40

LAYER_UNAVAILABLE_BASELINE = 0.1


@dataclass(frozen=True)
class CompositeScore:
    rule_score: float
    pattern_score: float
    judge_score: float
    composite: float
    verdict: Verdict


def composite(
    *,
    rule_score: float,
    pattern_score: float,
    judge_score: float,
    forced_verdict: Literal["hold", "block"] | None = None,
) -> CompositeScore:
    raw = RULE_WEIGHT * rule_score + PATTERN_WEIGHT * pattern_score + JUDGE_WEIGHT * judge_score
    score = max(0.0, min(1.0, raw))

    if forced_verdict == "block":
        verdict = Verdict.BLOCK
    elif forced_verdict == "hold":
        verdict = Verdict.HOLD
    elif score >= BLOCK_THRESHOLD:
        verdict = Verdict.BLOCK
    elif score >= HOLD_THRESHOLD:
        verdict = Verdict.HOLD
    else:
        verdict = Verdict.ALLOW

    return CompositeScore(
        rule_score=rule_score,
        pattern_score=pattern_score,
        judge_score=judge_score,
        composite=score,
        verdict=verdict,
    )
