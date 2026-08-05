"""The pattern layer learns from every human decision, which is fast to
adapt and just as fast to poison: a burst of decisions that all push the
same direction (a compromised or careless reviewer rubber-stamping holds,
say) can walk the boundary toward permissiveness a few degrees at a time.
These tests prove the detector actually fires on that kind of burst, stays
quiet on ordinary single decisions, and that a flagged model degrades to
the neutral baseline instead of trusting its own shifted opinion."""

from aegis.aegisai.model import DRIFT_THRESHOLD, DRIFT_WINDOW, PatternModel
from aegis.aegisai.scoring import LAYER_UNAVAILABLE_BASELINE

# A destructive-tier feature vector: the seed data associates this shape
# with "risky", so repeatedly labelling it "safe" is a real, adversarial
# pull on the boundary, not noise.
_DESTRUCTIVE_SHAPE = [0, 0, 0, 1, 0.9, 0.0, 0.0, 0.1, 0.0, 0.5]


def test_ordinary_single_decisions_do_not_flag_drift():
    model = PatternModel()
    for _ in range(DRIFT_WINDOW - 1):
        model.learn(_DESTRUCTIVE_SHAPE, risky=True)  # agrees with the seed prior
    assert model.drift_detected is False


def test_a_burst_of_boundary_reversing_decisions_flags_drift():
    model = PatternModel()
    for _ in range(DRIFT_WINDOW):
        # Repeatedly telling the model a destructive-shaped call is safe is
        # exactly the "rubber-stamped approvals" scenario this defends
        # against: an adversarial or careless run of decisions all pulling
        # the boundary the same direction.
        model.learn(_DESTRUCTIVE_SHAPE, risky=False)
    assert model.drift_detected is True
    assert model.last_drift_magnitude > DRIFT_THRESHOLD


def test_drift_flag_and_magnitude_survive_a_weights_round_trip():
    model = PatternModel()
    for _ in range(DRIFT_WINDOW):
        model.learn(_DESTRUCTIVE_SHAPE, risky=False)
    assert model.drift_detected is True

    restored = PatternModel.from_weights(model.to_weights())
    assert restored.drift_detected is True
    assert restored.last_drift_magnitude == model.last_drift_magnitude


async def test_flagged_model_degrades_pattern_score_to_the_neutral_baseline(
    db_session, monkeypatch
):
    """Once drift is flagged, the pattern layer must not trust the
    classifier's own (possibly poisoned) opinion. It should fall back to
    the same 'nothing known against it' baseline an unmatched rule uses,
    not a confident number."""
    from aegis.aegisai import patterns
    from aegis.aegisai.rules import CallContext
    from aegis.tools.registry import registry

    drifted_model = PatternModel()
    for _ in range(DRIFT_WINDOW):
        drifted_model.learn(_DESTRUCTIVE_SHAPE, risky=False)
    assert drifted_model.drift_detected is True

    async def fake_get_model(session):
        return drifted_model

    monkeypatch.setattr(patterns, "get_model", fake_get_model)

    tool = registry.require("delete_customer")
    context = CallContext(tool=tool, arguments={"customer_ids": ["CUST-1"]})

    score, _ = await patterns.score(
        context, session=db_session, agent_name="test-agent", step_index=0
    )
    assert score == LAYER_UNAVAILABLE_BASELINE
