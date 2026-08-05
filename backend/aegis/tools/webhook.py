"""A real external connector, not a synthetic one.

Every other tool in this demo (`aegis/tools/crm.py`) is an in-memory
function: predictable, controlled, and completely synthetic. None of them
has ever actually been intercepted mid-flight to a system with real
latency, a real network failure mode, or real partial-failure behavior,
which is exactly where a fail-closed guarantee gets tested for real.

`send_webhook_notification` makes a genuine outbound HTTPS request to
httpbin.org, a public request-echoing service built for exactly this kind
of testing, never a production third-party account. It has real timeouts,
real non-2xx responses, and a real network in between; AegisAI's chokepoint
sits in front of it the same way it would in front of a real payments or
notifications API.

Carries an idempotency key on every call, the same discipline API providers
like Stripe require for any action that might be retried: if a held call is
approved and the agent's own retry logic re-submits the same request, the
receiving system can tell it apart from a second, distinct notification.
AegisAI's own `guard()` already prevents the double-invocation this
protects against (a call only executes once, `ToolCall.executed` is set
the first time), so this is defense in depth for the tool's own caller,
not a gap AegisAI itself has.
"""

from __future__ import annotations

from uuid import uuid4

import httpx

from aegis.tools.registry import tool

SANDBOX_URL = "https://httpbin.org/post"
_TIMEOUT_SECONDS = 10.0


@tool(
    destructiveness="external",
    description="Send a webhook notification to an external system.",
)
def send_webhook_notification(event: str, payload: dict) -> dict:
    idempotency_key = str(uuid4())
    try:
        response = httpx.post(
            SANDBOX_URL,
            json={"event": event, "payload": payload},
            headers={"Idempotency-Key": idempotency_key},
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return {
            "status": "sent",
            "idempotency_key": idempotency_key,
            "http_status": response.status_code,
        }
    except httpx.HTTPError as exc:
        # A real network failure, not a synthetic one: the tool reports it
        # rather than raising, the same way a real integration would need
        # to handle a downstream outage without crashing the caller.
        return {
            "status": "failed",
            "idempotency_key": idempotency_key,
            "error": str(exc),
        }
