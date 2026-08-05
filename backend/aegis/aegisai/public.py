"""The stateless scoring path behind POST /v1/guard.

This is deliberately not `aegisai.core.guard()`. The internal guard owns
execution: on allow it runs the tool itself, on hold it blocks the request
until a human decides. A public API has no business owning execution for a
tool it has never seen, implemented by a caller in a language and process
this service knows nothing about. So this path only scores and persists,
the same rules -> pattern -> judge -> composite pipeline, and returns
immediately. Deciding what to do with a "hold" verdict is the caller's job.

Fails toward hold on any exception, exactly like the internal guard, for
the same reason: a scoring failure is not evidence a call is safe.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from aegis.aegisai import judge as judge_layer
from aegis.aegisai import patterns as pattern_layer
from aegis.aegisai.policy_store import get_active_rules
from aegis.aegisai.rules import CallContext, evaluate
from aegis.aegisai.scoring import composite
from aegis.models import CallStatus, ToolCall, Verdict
from aegis.tools.registry import resolve_or_external


async def score_public_call(
    *,
    session: AsyncSession,
    owner_label: str,
    api_key_id: str,
    policy_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    user_request: str,
    history: list[dict],
    agent_name: str | None = None,
) -> ToolCall:
    # agent_name is who the caller says is making the call; owner_label is
    # who the key belongs to. They usually match for a single-agent
    # integration but must not be conflated: one key can front several
    # agents, and holds/audit need to tell them apart.
    resolved_agent_name = agent_name or owner_label

    call = ToolCall(
        id=str(uuid4()),
        session_id=f"api:{api_key_id}",
        agent_name=resolved_agent_name,
        api_key_id=api_key_id,
        policy_id=policy_id,
        tool_name=tool_name,
        arguments=arguments,
        step_index=0,
        status=CallStatus.PENDING,
    )

    try:
        tool = resolve_or_external(tool_name)
        context = CallContext(tool=tool, arguments=arguments)

        rules = await get_active_rules(session, policy_id)
        rule_outcome = evaluate(context, rules)
        call.rule_score = rule_outcome.score
        call.matched_rules = rule_outcome.matched_rule_ids
        call.forced_by_rule = rule_outcome.forced_verdict is not None

        pattern_score, pattern_features = await pattern_layer.score(
            context, session=session, agent_name=resolved_agent_name, step_index=0
        )
        call.pattern_score = pattern_score
        call.pattern_features = pattern_features

        judge_score, judge_reasoning = await judge_layer.score(
            context, user_request=user_request, history=history
        )
        call.judge_score = judge_score
        call.judge_reasoning = judge_reasoning

        result = composite(
            rule_score=call.rule_score,
            pattern_score=call.pattern_score,
            judge_score=call.judge_score,
            forced_verdict=rule_outcome.forced_verdict,
        )
        call.composite_score = result.composite
        call.verdict = result.verdict
    except Exception as exc:  # noqa: BLE001 - see module docstring
        call.verdict = Verdict.HOLD
        call.failure_reason = f"{type(exc).__name__}: {exc}"

    if call.verdict != Verdict.HOLD:
        call.status = CallStatus.RESOLVED
        call.decided_by = "aegisai-auto"

    session.add(call)
    await session.commit()
    await session.refresh(call)
    return call
