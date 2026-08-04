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
    """A small, clearly separable seed set: destructive, large-batch, unseen
    calls are risky; read-only, familiar, small calls are not. This is not
    meant to be an accurate classifier on its own, only a reasonable prior
    to update from, which is exactly what a fresh deployment should ship
    with rather than an uninitialized model that has no opinion at all."""
    safe = [
        [1, 0, 0, 0, 0.02, 0.0, 0.0, 0.1, 1.0, 0.9],
        [1, 0, 0, 0, 0.02, 0.0, 0.0, 0.2, 1.0, 0.95],
        [0, 1, 0, 0, 0.02, 0.05, 0.0, 0.3, 1.0, 0.8],
        [0, 1, 0, 0, 0.02, 0.1, 0.0, 0.2, 1.0, 0.85],
        [0, 0, 1, 0, 0.02, 0.0, 0.0, 0.3, 1.0, 0.7],
    ]
    risky = [
        [0, 0, 0, 1, 0.4, 0.0, 0.0, 0.1, 0.0, 0.5],
        [0, 0, 0, 1, 1.0, 0.0, 0.0, 0.2, 0.0, 0.5],
        [0, 1, 0, 0, 0.02, 0.9, 0.0, 0.3, 0.0, 0.5],
        [0, 0, 1, 0, 0.02, 0.0, 1.0, 0.2, 0.0, 0.5],
        [0, 0, 0, 1, 0.2, 0.0, 0.0, 0.1, 0.0, 0.5],
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
