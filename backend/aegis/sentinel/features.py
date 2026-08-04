"""Feature extraction for the pattern layer.

A fixed, ordered vector so the online classifier's coefficients stay
interpretable across restarts. Every feature answers a question about the
*shape* of a call, never the destructive content on its own, since that is
already the rule layer's job. This layer's question is narrower: has this
agent done anything that looked like this before.
"""

from __future__ import annotations

from dataclasses import dataclass

from aegis.sentinel.rules import CallContext

FEATURE_NAMES = [
    "destructiveness_read",
    "destructiveness_write",
    "destructiveness_external",
    "destructiveness_destructive",
    "batch_size",
    "amount_bucket",
    "has_unallowlisted_recipient",
    "step_index",
    "shape_seen_before",
    "prior_approval_rate",
]

_ALLOWLISTED_DOMAINS = {"acmecorp.test", "brightlabs.test", "northwind.test", "aegisai.test"}

_DESTRUCTIVENESS_INDEX = {
    "read": 0,
    "write": 1,
    "external": 2,
    "destructive": 3,
}


@dataclass(frozen=True)
class HistorySignals:
    """What the caller already knows about this agent's past calls. Kept
    separate from feature extraction itself so extraction has no direct
    database dependency and stays trivially testable."""

    shape_seen_before: bool
    prior_approval_rate: float  # 0.5 means "no history", not "50% risky"


def shape_key(tool_name: str, arguments: dict) -> str:
    """The argument *shape*: which fields were used, not their values. Two
    refunds for different amounts share a shape; a refund and a bulk delete
    do not, even if both happen to touch the same customer id field name."""
    return f"{tool_name}:{','.join(sorted(arguments.keys()))}"


def extract(context: CallContext, *, step_index: int, history: HistorySignals) -> list[float]:
    vector = [0.0, 0.0, 0.0, 0.0]
    vector[_DESTRUCTIVENESS_INDEX.get(context.tool.destructiveness, 0)] = 1.0

    batch_size = 1
    for value in context.arguments.values():
        if isinstance(value, list):
            batch_size = max(batch_size, len(value))
    vector.append(min(batch_size / 50.0, 1.0))

    amount = 0.0
    for key in ("amount",):
        raw = context.arguments.get(key)
        if isinstance(raw, (int, float)):
            amount = float(raw)
    vector.append(min(amount / 1000.0, 1.0))

    recipient = context.arguments.get("to")
    has_bad_recipient = 0.0
    if isinstance(recipient, str) and "@" in recipient:
        domain = recipient.rsplit("@", 1)[-1].lower()
        has_bad_recipient = 0.0 if domain in _ALLOWLISTED_DOMAINS else 1.0
    vector.append(has_bad_recipient)

    vector.append(min(step_index / 10.0, 1.0))
    vector.append(1.0 if history.shape_seen_before else 0.0)
    vector.append(history.prior_approval_rate)

    return vector
