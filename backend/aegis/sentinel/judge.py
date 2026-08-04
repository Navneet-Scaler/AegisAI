"""The LLM judge layer: does this call actually follow from what the user
asked, or does it look hijacked by something the agent read along the way.

Delegates to the configured `LLMProvider.judge()`, wrapped in a strict
timeout. Any exception, including a timeout, propagates out of `score()`
rather than being caught here: `Sentinel.guard`'s outer try/except is the one
place that turns a failure into a `hold`, and this layer must not quietly
absorb a failure into a low score instead.
"""

from __future__ import annotations

import asyncio

from aegis.agent.factory import get_provider
from aegis.agent.provider import ToolCallRequest
from aegis.sentinel.rules import CallContext

JUDGE_TIMEOUT_SECONDS = 8.0


async def score(
    context: CallContext, *, user_request: str, history: list[dict]
) -> tuple[float, str | None]:
    provider = get_provider()
    proposed_call = ToolCallRequest(context.tool.name, context.arguments)

    verdict = await asyncio.wait_for(
        provider.judge(user_request=user_request, history=history, proposed_call=proposed_call),
        timeout=JUDGE_TIMEOUT_SECONDS,
    )

    risk = max(0.0, min(1.0, verdict.risk))
    return risk, verdict.reasoning
