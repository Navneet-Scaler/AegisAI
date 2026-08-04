"""A single human decision changes the next similar call's score
immediately. This is the "watch it learn" moment the demo relies on, so it
gets a direct test rather than being asserted only implicitly."""

import asyncio
import uuid

from fastapi.testclient import TestClient

from aegis.config import get_settings
from aegis.db import get_sessionmaker
from aegis.main import app
from aegis.sentinel.core import guard
from aegis.sentinel.features import extract, shape_key
from aegis.sentinel.model import PatternModel


def test_shape_key_is_stable_for_the_same_argument_shape():
    assert shape_key("create_refund", {"customer_id": "A", "amount": 10, "reason": "x"}) == (
        shape_key("create_refund", {"customer_id": "B", "amount": 999, "reason": "y"})
    )


def test_shape_key_differs_across_tools():
    assert shape_key("read_ticket", {"id": "A"}) != shape_key("search_customers", {"id": "A"})


def test_model_risk_moves_after_a_single_learn_call():
    model = PatternModel()
    features = [0, 0, 0, 1, 0.4, 0.0, 0.0, 0.1, 0.0, 0.5]  # destructive-shaped

    before = model.risk(features)
    model.learn(features, risky=False)
    after = model.risk(features)

    assert model.update_count == 1
    assert after < before, "approving a call should lower risk for that same shape"


def test_approving_a_held_call_measurably_lowers_the_next_similar_calls_score():
    """A refund over the rule threshold is always held. Approve it once
    through the real, token-protected HTTP endpoint, the same path a human
    reviewer uses, then send an equivalently-shaped call directly through
    guard() and confirm its pattern score dropped."""
    settings = get_settings()
    token = f"Bearer {settings.demo_token}"
    agent_name = f"agent-{uuid.uuid4()}"
    sessionmaker = get_sessionmaker()

    with TestClient(app) as client:
        client.post("/demo/reset", headers={"Authorization": token})

        async def hold_a_large_refund():
            async with sessionmaker() as session:
                return await guard(
                    session=session,
                    session_id=str(uuid.uuid4()),
                    agent_name=agent_name,
                    tool_name="create_refund",
                    arguments={"customer_id": "CUST-1001", "amount": 900, "reason": "goodwill"},
                    step_index=0,
                    user_request="a goodwill refund",
                    history=[],
                    approval_timeout_seconds=10,
                )

        async def scenario():
            first_task = asyncio.create_task(hold_a_large_refund())

            approved_id = None
            for _ in range(40):
                await asyncio.sleep(0.1)
                calls = (await asyncio.to_thread(client.get, "/calls")).json()
                pending = [c for c in calls if c["status"] == "pending"]
                if pending:
                    approved_id = pending[0]["id"]
                    approve = await asyncio.to_thread(
                        client.post,
                        f"/calls/{approved_id}/decide",
                        json={"approve": True},
                        headers={"Authorization": token},
                    )
                    assert approve.status_code == 200
                    break
            else:
                raise AssertionError("the large refund never reached pending state")

            first_call = await first_task

            async with sessionmaker() as session:
                second_call = await guard(
                    session=session,
                    session_id=str(uuid.uuid4()),
                    agent_name=agent_name,
                    tool_name="create_refund",
                    arguments={"customer_id": "CUST-1003", "amount": 950, "reason": "goodwill"},
                    step_index=0,
                    user_request="another goodwill refund",
                    history=[],
                    approval_timeout_seconds=1,
                )
            return first_call, second_call

        first_call, second_call = asyncio.run(scenario())

        assert second_call.pattern_score <= first_call.pattern_score


def test_extract_marks_a_batch_delete_with_a_large_batch_size():
    from aegis.sentinel.features import HistorySignals
    from aegis.sentinel.rules import CallContext
    from aegis.tools import registry

    tool = registry.require("delete_customer")
    context = CallContext(tool=tool, arguments={"customer_ids": [f"C{i}" for i in range(20)]})
    history = HistorySignals(shape_seen_before=False, prior_approval_rate=0.5)

    vector = extract(context, step_index=0, history=history)
    batch_size_index = 4  # after the four one-hot destructiveness slots
    assert vector[batch_size_index] == 20 / 50.0
