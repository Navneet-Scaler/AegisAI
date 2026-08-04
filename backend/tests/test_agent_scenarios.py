"""POST /agent/run's optional scenario field, in mock/replay mode: "refund"
always allows, "delete" always holds via the destructive-delete rule. This
is what makes the README's curl example and the dashboard's two demo
buttons actually reachable through the API, rather than only through a
direct call to guard() in tests."""

from fastapi.testclient import TestClient

from aegis.main import app


def test_refund_scenario_completes_without_needing_approval():
    with TestClient(app) as client:
        response = client.post("/agent/run", json={"request": "refund it", "scenario": "refund"})
        assert response.status_code == 200
        body = response.json()
        assert body["stopped_reason"] == "final_answer"
        assert all(step["verdict"] == "allow" for step in body["history"])


def test_delete_scenario_holds_until_approved():
    """The request only returns once the held call is resolved, so this
    approves it from a second thread while the first request is still
    in flight, the same shape as a human reviewing the live dashboard
    while an agent run is in progress."""
    import threading

    from aegis.config import get_settings

    token = f"Bearer {get_settings().demo_token}"
    result = {}

    with TestClient(app) as client:

        def run():
            result["response"] = client.post(
                "/agent/run",
                json={"request": "remove the customer", "scenario": "delete"},
            )

        thread = threading.Thread(target=run)
        thread.start()

        approved = False
        for _ in range(50):
            calls = client.get("/calls").json()
            pending = [
                c for c in calls if c["tool_name"] == "delete_customer" and c["status"] == "pending"
            ]
            if pending:
                approve = client.post(
                    f"/calls/{pending[0]['id']}/decide",
                    json={"approve": True},
                    headers={"Authorization": token},
                )
                assert approve.status_code == 200
                approved = True
                break
            import time

            time.sleep(0.1)

        assert approved, "the delete_customer call never reached pending state"
        thread.join(timeout=10)

    response = result["response"]
    assert response.status_code == 200
    body = response.json()
    delete_step = next(s for s in body["history"] if s["tool_name"] == "delete_customer")
    assert delete_step["verdict"] == "allow"
