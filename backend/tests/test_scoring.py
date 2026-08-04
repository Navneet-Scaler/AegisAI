from aegis.models import Verdict
from aegis.sentinel.scoring import composite


def test_low_scores_across_all_layers_allow():
    result = composite(rule_score=0.1, pattern_score=0.1, judge_score=0.1)
    assert result.verdict == Verdict.ALLOW


def test_high_composite_blocks_even_without_a_forced_rule():
    result = composite(rule_score=0.9, pattern_score=0.9, judge_score=0.9)
    assert result.verdict == Verdict.BLOCK


def test_forced_hold_wins_even_if_the_raw_score_would_allow():
    result = composite(rule_score=0.1, pattern_score=0.1, judge_score=0.1, forced_verdict="hold")
    assert result.verdict == Verdict.HOLD


def test_forced_block_wins_even_if_the_raw_score_would_allow():
    result = composite(rule_score=0.1, pattern_score=0.1, judge_score=0.1, forced_verdict="block")
    assert result.verdict == Verdict.BLOCK


def test_composite_is_clamped_to_the_unit_interval():
    result = composite(rule_score=1.0, pattern_score=1.0, judge_score=1.0)
    assert 0.0 <= result.composite <= 1.0
