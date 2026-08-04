"""The rule layer: static policy that can force a verdict outright.

Rules are declarative YAML rather than code, so the policy in `seed/rules.yaml`
can be edited without a redeploy. When no rule matches at all, the rule
component contributes `RULE_NO_MATCH_BASELINE`, not zero. Zero would assert
"affirmatively safe", which no rule ever claimed; the baseline means "nothing
known against it", which keeps the composite score meaningful instead of
being three numbers averaged for no better reason than that three numbers
existed.

A rules file that is missing or fails to parse is a fail-closed condition
handled by the caller (`aegis.aegisai.core`), not swallowed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from aegis.tools.registry import Tool

RULE_NO_MATCH_BASELINE = 0.1

_RULES_PATH = Path(__file__).resolve().parent.parent / "seed" / "rules.yaml"


@dataclass(frozen=True)
class RuleOutcome:
    score: float
    matched_rule_ids: list[str]
    forced_verdict: Literal["hold", "block"] | None


@dataclass(frozen=True)
class CallContext:
    """What a rule is allowed to see about a proposed call."""

    tool: Tool
    arguments: dict[str, Any]


def load_rules(path: Path = _RULES_PATH) -> list[dict[str, Any]]:
    """Raises if the file is missing or malformed. The caller decides that
    this means the app should refuse to start (in production) or every call
    should hold (at request time)."""
    text = path.read_text()
    data = yaml.safe_load(text)
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list):
        raise ValueError(f"{path} did not contain a top-level 'rules' list")
    return rules


def evaluate(context: CallContext, rules: list[dict[str, Any]]) -> RuleOutcome:
    matched: list[dict[str, Any]] = [r for r in rules if _matches(r.get("match", {}), context)]

    if not matched:
        return RuleOutcome(score=RULE_NO_MATCH_BASELINE, matched_rule_ids=[], forced_verdict=None)

    score = max(RULE_NO_MATCH_BASELINE, max(float(r.get("score", 0.0)) for r in matched))

    forced: Literal["hold", "block"] | None = None
    for r in matched:
        candidate = r.get("force")
        if candidate == "block":
            forced = "block"
            break
        if candidate == "hold" and forced is None:
            forced = "hold"

    return RuleOutcome(
        score=min(score, 1.0),
        matched_rule_ids=[r["id"] for r in matched],
        forced_verdict=forced,
    )


def _matches(predicate: dict[str, Any], context: CallContext) -> bool:
    if "tool_in" in predicate and context.tool.name not in predicate["tool_in"]:
        return False

    if "destructiveness_in" in predicate:
        if context.tool.destructiveness not in predicate["destructiveness_in"]:
            return False

    if "arg_gt" in predicate:
        for arg_name, threshold in predicate["arg_gt"].items():
            value = context.arguments.get(arg_name)
            if not isinstance(value, (int, float)) or value <= threshold:
                return False

    if "arg_len_gt" in predicate:
        for arg_name, threshold in predicate["arg_len_gt"].items():
            value = context.arguments.get(arg_name)
            if not isinstance(value, (list, str)) or len(value) <= threshold:
                return False

    if "arg_domain_not_in" in predicate:
        for arg_name, allowed_domains in predicate["arg_domain_not_in"].items():
            value = context.arguments.get(arg_name)
            if not isinstance(value, str) or "@" not in value:
                return False
            domain = value.rsplit("@", 1)[-1].lower()
            if domain in {d.lower() for d in allowed_domains}:
                return False

    return True
