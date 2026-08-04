import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from aegis.config import get_settings
from aegis.db import get_sessionmaker
from aegis.main import app
from aegis.models import Verdict
from aegis.sentinel.core import guard


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_decide_without_a_token_is_rejected(client):
    response = client.post("/calls/does-not-exist/decide", json={"approve": True})
    assert response.status_code == 401


def test_decide_with_the_wrong_token_is_rejected(client):
    response = client.post(
        "/calls/does-not-exist/decide",
        json={"approve": True},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401


def test_read_endpoints_do_not_require_a_token(client):
    response = client.get("/calls")
    assert response.status_code == 200


def test_approving_a_held_call_through_the_real_endpoint_lets_it_execute(client):
    """delete_customer is always held by policy. Approve it through the same
    token-protected HTTP endpoint a human reviewer would use, and confirm
    Sentinel resumes and actually executes the call."""
    settings = get_settings()
    token = f"Bearer {settings.demo_token}"
    sessionmaker = get_sessionmaker()

    async def hold_via_guard():
        async with sessionmaker() as session:
            return await guard(
                session=session,
                session_id=str(uuid.uuid4()),
                agent_name="test-agent",
                tool_name="delete_customer",
                arguments={"customer_ids": ["CUST-1002"]},
                step_index=0,
                user_request="delete customer CUST-1002",
                history=[],
                approval_timeout_seconds=10,
            )

    async def scenario():
        guard_task = asyncio.create_task(hold_via_guard())

        for _ in range(40):
            await asyncio.sleep(0.1)
            calls = (await asyncio.to_thread(client.get, "/calls")).json()
            pending = [c for c in calls if c["status"] == "pending"]
            if pending:
                approve = await asyncio.to_thread(
                    client.post,
                    f"/calls/{pending[0]['id']}/decide",
                    json={"approve": True},
                    headers={"Authorization": token},
                )
                assert approve.status_code == 200
                break
        else:
            pytest.fail("delete_customer call never reached pending state")

        return await guard_task

    call = asyncio.run(scenario())
    assert call.verdict == Verdict.ALLOW
    assert call.executed
    assert call.decided_by == "reviewer"
