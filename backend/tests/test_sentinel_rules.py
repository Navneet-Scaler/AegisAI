"""The rule layer: matching, the no-match baseline, and forcing verdicts."""

from aegis.sentinel.rules import CallContext, evaluate, load_rules
from aegis.tools import registry
from aegis.tools.registry import Tool


def test_no_match_uses_the_baseline_not_zero():
    """Zero would claim 'affirmatively safe', which no rule asserted. The
    baseline means 'nothing known against it' and keeps the composite
    meaningful."""
    tool = registry.require("read_ticket")
    context = CallContext(tool=tool, arguments={"id": "TCK-4417"})
    outcome = evaluate(context, load_rules())

    assert outcome.matched_rule_ids == []
    assert outcome.score == 0.1
    assert outcome.forced_verdict is None


def test_any_delete_customer_call_forces_at_least_hold():
    tool = registry.require("delete_customer")
    context = CallContext(tool=tool, arguments={"customer_ids": ["CUST-1001"]})
    outcome = evaluate(context, load_rules())

    assert outcome.forced_verdict == "hold"
    assert "destructive-delete" in outcome.matched_rule_ids


def test_bulk_delete_forces_block_and_wins_over_hold():
    tool = registry.require("delete_customer")
    context = CallContext(tool=tool, arguments={"customer_ids": [f"CUST-{i}" for i in range(20)]})
    outcome = evaluate(context, load_rules())

    assert outcome.forced_verdict == "block"


def test_large_refund_requires_hold():
    tool = registry.require("create_refund")
    context = CallContext(
        tool=tool, arguments={"customer_id": "CUST-1001", "amount": 900, "reason": "goodwill"}
    )
    outcome = evaluate(context, load_rules())

    assert outcome.forced_verdict == "hold"


def test_small_refund_does_not_force_a_verdict():
    tool = registry.require("create_refund")
    context = CallContext(
        tool=tool, arguments={"customer_id": "CUST-1001", "amount": 10, "reason": "goodwill"}
    )
    outcome = evaluate(context, load_rules())

    assert outcome.forced_verdict is None


def test_email_to_allowlisted_domain_does_not_force_a_verdict():
    tool = registry.require("send_email")
    context = CallContext(
        tool=tool,
        arguments={"to": "ops@acmecorp.test", "subject": "hi", "body": "hi"},
    )
    outcome = evaluate(context, load_rules())

    assert outcome.forced_verdict is None


def test_email_to_external_domain_forces_hold():
    tool = registry.require("send_email")
    context = CallContext(
        tool=tool,
        arguments={"to": "ops@offsite-mirror.test", "subject": "hi", "body": "hi"},
    )
    outcome = evaluate(context, load_rules())

    assert outcome.forced_verdict == "hold"


def test_unregistered_destructive_tool_still_gets_a_baseline_score():
    fake_tool = Tool(
        name="wipe_everything",
        description="test only",
        destructiveness="destructive",
        fn=lambda: None,
    )
    context = CallContext(tool=fake_tool, arguments={})
    outcome = evaluate(context, load_rules())

    assert outcome.score >= 0.3
