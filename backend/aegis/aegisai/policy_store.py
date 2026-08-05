"""Versioned, dry-runnable policy storage.

A rule change here gets the same rigor as a code change: a reviewable
diff (dry-run against historical calls before it goes live) and a rollback
path (every prior version stays on record, reactivating one is a rollback),
not a silent overwrite of a YAML file that every key scored against that
policy quietly starts trusting.

`policy_id` values that were never edited through this module have no rows
in `PolicyVersion` at all. `get_active_rules` falls back to the YAML file
under `seed/policies/<policy_id>.yaml` for those, so shipping a new policy
file continues to work with no database write, and editing a policy for
the first time here doesn't require pre-seeding the database with
everything `seed/policies/` already ships.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.aegisai.rules import CallContext, evaluate, load_rules
from aegis.models import CallStatus, PolicyVersion, ToolCall
from aegis.tools.registry import resolve_or_external

# How many resolved calls a dry run inspects. Enough to be representative
# of a fresh demo, cheap enough not to need a background job. Newest first,
# so a dry run reflects what the policy has actually been facing lately,
# not the oldest rows in the table.
DRY_RUN_SAMPLE_SIZE = 200


def validate_rules_shape(rules: Any) -> list[dict[str, Any]]:
    """The same shape `aegisai.rules.evaluate` expects: a list of dicts,
    each with at least an `id` and a `match`. Raised errors are caught by
    the route and turned into a 400, not a policy that silently fails to
    load the next time a call is scored against it."""
    if not isinstance(rules, list) or not rules:
        raise ValueError("rules must be a non-empty list")
    seen_ids: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("each rule must be an object")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("each rule needs a non-empty string 'id'")
        if rule_id in seen_ids:
            raise ValueError(f"duplicate rule id: {rule_id!r}")
        seen_ids.add(rule_id)
        if not isinstance(rule.get("match"), dict):
            raise ValueError(f"rule {rule_id!r} needs a 'match' object")
        force = rule.get("force")
        if force is not None and force not in ("hold", "block"):
            raise ValueError(f"rule {rule_id!r}: force must be 'hold', 'block', or omitted")
    return rules


async def get_active_version(session: AsyncSession, policy_id: str) -> PolicyVersion | None:
    result = await session.execute(
        select(PolicyVersion).where(PolicyVersion.policy_id == policy_id, PolicyVersion.is_active)
    )
    return result.scalar_one_or_none()


async def get_active_rules(session: AsyncSession, policy_id: str) -> list[dict[str, Any]]:
    active = await get_active_version(session, policy_id)
    if active is not None:
        return active.rules
    # No edit has ever been saved for this policy: fall back to the YAML
    # file it shipped with. Raises the same way load_rules always has if
    # that file is missing or malformed, the fail-closed path the caller
    # already handles.
    return load_rules(policy_id)


async def list_versions(session: AsyncSession, policy_id: str) -> list[PolicyVersion]:
    result = await session.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .order_by(PolicyVersion.version.desc())
    )
    return list(result.scalars().all())


async def _next_version_number(session: AsyncSession, policy_id: str) -> int:
    result = await session.execute(
        select(func.max(PolicyVersion.version)).where(PolicyVersion.policy_id == policy_id)
    )
    highest = result.scalar_one_or_none()
    return (highest or 0) + 1


async def save_draft(
    session: AsyncSession,
    *,
    policy_id: str,
    rules: list[dict[str, Any]],
    description: str = "",
    created_by: str = "dashboard",
) -> PolicyVersion:
    """Saves a new version without activating it. The first version ever
    saved for a policy_id is also its first opportunity to be dry-run
    against history before anyone commits to it."""
    validate_rules_shape(rules)
    version = PolicyVersion(
        id=str(uuid4()),
        policy_id=policy_id,
        version=await _next_version_number(session, policy_id),
        rules=rules,
        description=description,
        created_by=created_by,
        is_active=False,
    )
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return version


async def activate_version(
    session: AsyncSession, *, policy_id: str, version_id: str
) -> PolicyVersion:
    """Activating an old version is how a rollback works: there is no
    separate rollback operation, just activating something that already
    exists in the version history."""
    result = await session.execute(
        select(PolicyVersion).where(
            PolicyVersion.id == version_id, PolicyVersion.policy_id == policy_id
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise ValueError(f"No version {version_id!r} for policy {policy_id!r}")

    currently_active = await get_active_version(session, policy_id)
    if currently_active is not None and currently_active.id != target.id:
        currently_active.is_active = False
        session.add(currently_active)

    target.is_active = True
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return target


@dataclass(frozen=True)
class DryRunCallResult:
    call_id: str
    tool_name: str
    actual_verdict_tier: str  # what the composite score's rule component implied, roughly
    proposed_forced_verdict: str | None
    matched_rule_ids: list[str]
    changed: bool


@dataclass(frozen=True)
class DryRunSummary:
    sample_size: int
    would_change: int
    newly_forced_hold: int
    newly_forced_block: int
    no_longer_forced: int
    results: list[DryRunCallResult]


async def dry_run(
    session: AsyncSession, *, proposed_rules: list[dict[str, Any]], policy_id: str
) -> DryRunSummary:
    """Re-evaluates `proposed_rules` against the most recent resolved calls
    that were actually scored under `policy_id`, and compares the result to
    what the rule layer forced (or didn't) at the time. This is the WAF
    "count mode before block mode" pattern: never activate a policy without
    first seeing its blast radius against real traffic, or in a fresh demo
    with little history, the traffic that exists.
    """
    validate_rules_shape(proposed_rules)

    rows_result = await session.execute(
        select(ToolCall)
        .where(ToolCall.status == CallStatus.RESOLVED, ToolCall.policy_id == policy_id)
        .order_by(ToolCall.created_at.desc())
        .limit(DRY_RUN_SAMPLE_SIZE)
    )
    rows = list(rows_result.scalars().all())

    results: list[DryRunCallResult] = []
    newly_hold = 0
    newly_block = 0
    no_longer_forced = 0

    for row in rows:
        tool = resolve_or_external(row.tool_name)
        context = CallContext(tool=tool, arguments=row.arguments)
        outcome = evaluate(context, proposed_rules)

        was_forced = row.forced_by_rule
        now_forced = outcome.forced_verdict is not None
        # Compare against which rules matched, not against row.verdict: the
        # stored verdict can be a held call that later timed out to block,
        # or one a human approved, neither of which is the rule layer's own
        # output at scoring time. matched_rules is never touched after the
        # fact, so it is the only reliable "what did the rules say" record
        # to diff a proposed policy against.
        changed = was_forced != now_forced or (
            was_forced and now_forced and set(row.matched_rules) != set(outcome.matched_rule_ids)
        )

        if changed:
            if outcome.forced_verdict == "hold" and not was_forced:
                newly_hold += 1
            elif outcome.forced_verdict == "block" and not was_forced:
                newly_block += 1
            elif was_forced and not now_forced:
                no_longer_forced += 1

        results.append(
            DryRunCallResult(
                call_id=row.id,
                tool_name=row.tool_name,
                actual_verdict_tier=row.verdict.value,
                proposed_forced_verdict=outcome.forced_verdict,
                matched_rule_ids=outcome.matched_rule_ids,
                changed=changed,
            )
        )

    return DryRunSummary(
        sample_size=len(rows),
        would_change=sum(1 for r in results if r.changed),
        newly_forced_hold=newly_hold,
        newly_forced_block=newly_block,
        no_longer_forced=no_longer_forced,
        results=results,
    )
