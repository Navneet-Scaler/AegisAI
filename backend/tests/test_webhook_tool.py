"""send_webhook_notification is a real outbound HTTP call, not a synthetic
in-memory function like the rest of the mock CRM. The suite mocks the
actual network call here, real network access is not something a CI run
should depend on for a passing test, but the guard-mediated interception
and idempotency-key behavior are real. `scripts/verify_webhook_live.py`
(not part of this suite) exercises it against the real sandbox."""

from unittest.mock import MagicMock, patch

from aegis.tools import registry
from aegis.tools.webhook import SANDBOX_URL, send_webhook_notification


def test_webhook_tool_is_registered():
    tool = registry.require("send_webhook_notification")
    assert tool.destructiveness == "external"


def test_successful_call_returns_sent_with_a_fresh_idempotency_key():
    mock_response = MagicMock(status_code=200)
    mock_response.raise_for_status.return_value = None

    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = send_webhook_notification(event="refund_issued", payload={"amount": 42})

    assert result["status"] == "sent"
    assert result["http_status"] == 200
    assert result["idempotency_key"]

    call_kwargs = mock_post.call_args
    assert call_kwargs.args[0] == SANDBOX_URL
    assert call_kwargs.kwargs["headers"]["Idempotency-Key"] == result["idempotency_key"]


def test_two_calls_get_different_idempotency_keys():
    mock_response = MagicMock(status_code=200)
    mock_response.raise_for_status.return_value = None

    with patch("httpx.post", return_value=mock_response):
        first = send_webhook_notification(event="a", payload={})
        second = send_webhook_notification(event="a", payload={})

    assert first["idempotency_key"] != second["idempotency_key"]


def test_a_real_network_failure_is_reported_not_raised():
    """The whole point of this tool over the synthetic ones: a downstream
    outage is a real possibility, and the tool has to degrade to a
    reported failure, not crash whatever called it."""
    import httpx as httpx_module

    with patch("httpx.post", side_effect=httpx_module.ConnectTimeout("timed out")):
        result = send_webhook_notification(event="a", payload={})

    assert result["status"] == "failed"
    assert "timed out" in result["error"].lower()
    assert result["idempotency_key"]


async def test_guard_intercepts_the_real_tool_the_same_as_any_other(db_session):
    """AegisAI.guard() does not know or care that this tool makes a real
    network call instead of touching an in-memory dict; it is scored and
    gated exactly like delete_customer or create_refund."""
    from aegis.aegisai.core import guard

    mock_response = MagicMock(status_code=200)
    mock_response.raise_for_status.return_value = None

    with patch("httpx.post", return_value=mock_response):
        call = await guard(
            session=db_session,
            session_id="test-session",
            agent_name="test-agent",
            tool_name="send_webhook_notification",
            arguments={"event": "refund_issued", "payload": {"amount": 42}},
            step_index=0,
            user_request="notify the customer",
            history=[],
            approval_timeout_seconds=1,
        )

    assert call.verdict.value == "allow"
    assert call.executed is True
    assert "sent" in call.result
