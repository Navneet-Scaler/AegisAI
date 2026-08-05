"""AegisAI.guard: the single chokepoint every tool call must pass through.

The agent loop has no other path to a tool executor. Anything that goes
wrong anywhere in the scoring pipeline, rules file, pattern model, judge
call, database write, resolves to a `hold` verdict, recorded with a
`failure_reason`. Nothing here can silently resolve to `allow`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from aegis.aegisai import approvals
from aegis.aegisai import judge as judge_layer
from aegis.aegisai import patterns as pattern_layer
from aegis.aegisai.rules import CallContext, evaluate, load_rules
from aegis.aegisai.scoring import composite
from aegis.models import CallStatus, ToolCall, Verdict
from aegis.tools.registry import registry


def _now() -> datetime:
    return datetime.now(UTC)


async def guard(
    *,
    session: AsyncSession,
    session_id: str,
    agent_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    step_index: int,
    user_request: str,
    history: list[dict[str, Any]],
    approval_timeout_seconds: int,
    policy_id: str = "default",
    api_key_id: str | None = None,
) -> ToolCall:
    call = ToolCall(
        id=str(uuid4()),
        session_id=session_id,
        agent_name=agent_name,
        api_key_id=api_key_id,
        tool_name=tool_name,
        arguments=arguments,
        step_index=step_index,
        status=CallStatus.PENDING,
    )

    try:
        forced_verdict = await _score(
            call,
            session=session,
            agent_name=agent_name,
            tool_name=tool_name,
            arguments=arguments,
            step_index=step_index,
            user_request=user_request,
            history=history,
            policy_id=policy_id,
        )
        result = composite(
            rule_score=call.rule_score or 0.0,
            pattern_score=call.pattern_score or 0.0,
            judge_score=call.judge_score or 0.0,
            forced_verdict=forced_verdict,
        )
        call.composite_score = result.composite
        call.verdict = result.verdict
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see module docstring
        call.verdict = Verdict.HOLD
        call.failure_reason = f"{type(exc).__name__}: {exc}"

    session.add(call)
    await session.commit()
    await session.refresh(call)

    if call.verdict == Verdict.BLOCK:
        _resolve(call, decided_by="aegisai")
        session.add(call)
        await session.commit()
        await session.refresh(call)
        return call

    if call.verdict == Verdict.ALLOW:
        _execute(call, arguments)
        _resolve(call, decided_by="aegisai-auto-allow")
        session.add(call)
        await session.commit()
        await session.refresh(call)
        return call

    # HOLD: wait on the persisted row, not on in-process state.
    await approvals.wait_for_decision(
        call_id=call.id, session=session, timeout_seconds=approval_timeout_seconds
    )
    await session.refresh(call)

    if call.status != CallStatus.RESOLVED:
        call.verdict = Verdict.BLOCK
        _resolve(call, decided_by="aegisai-timeout")

    if call.verdict == Verdict.ALLOW and not call.executed:
        _execute(call, arguments)

    session.add(call)
    await session.commit()
    await session.refresh(call)
    return call


def _resolve(call: ToolCall, *, decided_by: str) -> None:
    call.status = CallStatus.RESOLVED
    call.decided_by = decided_by
    call.decided_at = _now()


async def _score(
    call: ToolCall,
    *,
    session: AsyncSession,
    agent_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    step_index: int,
    user_request: str,
    history: list[dict[str, Any]],
    policy_id: str = "default",
) -> str | None:
    """Runs all three layers and writes their sub-scores onto `call`. Returns
    the forced verdict from the rule layer, if any, for the caller to pass
    into the composite calculation."""
    tool = registry.require(tool_name)
    context = CallContext(tool=tool, arguments=arguments)

    rules = load_rules(policy_id)
    rule_outcome = evaluate(context, rules)
    call.rule_score = rule_outcome.score
    call.matched_rules = rule_outcome.matched_rule_ids
    call.forced_by_rule = rule_outcome.forced_verdict is not None

    pattern_score, pattern_features = await pattern_layer.score(
        context, session=session, agent_name=agent_name, step_index=step_index
    )
    call.pattern_score = pattern_score
    call.pattern_features = pattern_features

    judge_score, judge_reasoning = await judge_layer.score(
        context, user_request=user_request, history=history
    )
    call.judge_score = judge_score
    call.judge_reasoning = judge_reasoning

    return rule_outcome.forced_verdict


def _execute(call: ToolCall, arguments: dict[str, Any]) -> None:
    tool = registry.get(call.tool_name)
    if tool is None:
        call.result = f"error: unknown tool {call.tool_name}"
        return
    try:
        result = tool.fn(**arguments)
        call.result = str(result)
        call.executed = True
    except Exception as exc:  # noqa: BLE001
        call.result = f"error: {exc}"
