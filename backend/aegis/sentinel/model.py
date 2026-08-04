"""The online pattern classifier.

`SGDClassifier(loss="log_loss")` with `partial_fit` rather than a periodic
batch retrain: every single human decision updates the weights immediately,
so the "watch it learn" moment fires reliably inside a short demo, and
"online learning" is an accurate claim rather than an aspirational one.

Seeded once from a small synthetic dataset at construction so the model has
an opinion before any human decision exists, then persisted to the
`ModelState` row after every `partial_fit` call so weights survive restarts.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import SGDClassifier

from aegis.sentinel.features import FEATURE_NAMES

_CLASSES = np.array([0, 1])  # 0 = safe, 1 = risky


def _synthetic_seed() -> tuple[list[list[float]], list[int]]:
    """A small, clearly separable seed set: destructive, large-batch,
    high-amount, or wrong-recipient calls are risky; everything else is not.

    Both classes span both `shape_seen_before` states on purpose. A first
    ever call to a brand-new tool must not read as risky on that basis
    alone, since "no history" means "nothing known against it" everywhere
    else in this system, not "presumed dangerous". If every safe example
    here had `shape_seen_before=1` and every risky example had it at 0, the
    model would learn "unfamiliar" as the risk signal instead of what should
    actually predict it: destructiveness, batch size, amount, and recipient.

    This is not meant to be an accurate classifier on its own, only a
    reasonable, non-perverse prior to update from, which is what a fresh
    deployment should ship with rather than an uninitialized model with no
    opinion at all.
    """
    safe = [
        [1, 0, 0, 0, 0.02, 0.0, 0.0, 0.1, 1.0, 0.9],
        [1, 0, 0, 0, 0.02, 0.0, 0.0, 0.0, 0.0, 0.5],
        [0, 1, 0, 0, 0.02, 0.05, 0.0, 0.3, 1.0, 0.8],
        [0, 1, 0, 0, 0.02, 0.1, 0.0, 0.0, 0.0, 0.5],
        [0, 0, 1, 0, 0.02, 0.0, 0.0, 0.3, 1.0, 0.7],
        [0, 0, 1, 0, 0.02, 0.0, 0.0, 0.0, 0.0, 0.5],
    ]
    risky = [
        [0, 0, 0, 1, 0.4, 0.0, 0.0, 0.1, 0.0, 0.5],
        [0, 0, 0, 1, 1.0, 0.0, 0.0, 0.2, 1.0, 0.9],
        [0, 1, 0, 0, 0.02, 0.9, 0.0, 0.3, 0.0, 0.5],
        [0, 1, 0, 0, 0.02, 0.95, 0.0, 0.2, 1.0, 0.8],
        [0, 0, 1, 0, 0.02, 0.0, 1.0, 0.2, 0.0, 0.5],
        [0, 0, 1, 0, 0.02, 0.0, 1.0, 0.1, 1.0, 0.6],
        [0, 0, 0, 1, 0.2, 0.0, 0.0, 0.1, 1.0, 0.85],
    ]
    features = safe + risky
    labels = [0] * len(safe) + [1] * len(risky)
    return features, labels


class PatternModel:
    def __init__(self) -> None:
        self._clf = SGDClassifier(loss="log_loss", random_state=7)
        seed_x, seed_y = _synthetic_seed()
        self._clf.partial_fit(np.array(seed_x), np.array(seed_y), classes=_CLASSES)
        self.update_count = 0

    def risk(self, features: list[float]) -> float:
        proba = self._clf.predict_proba([features])[0]
        # index 1 is the "risky" class
        return float(proba[1])

    def learn(self, features: list[float], *, risky: bool) -> None:
        label = 1 if risky else 0
        self._clf.partial_fit([features], [label])
        self.update_count += 1

    def to_weights(self) -> dict:
        return {
            "coef": self._clf.coef_.tolist(),
            "intercept": self._clf.intercept_.tolist(),
            "classes": self._clf.classes_.tolist(),
            "update_count": self.update_count,
            "feature_names": FEATURE_NAMES,
        }

    @classmethod
    def from_weights(cls, weights: dict) -> PatternModel:
        model = cls()
        model._clf.coef_ = np.array(weights["coef"])
        model._clf.intercept_ = np.array(weights["intercept"])
        model._clf.classes_ = np.array(weights["classes"])
        model.update_count = weights.get("update_count", 0)
        return model
