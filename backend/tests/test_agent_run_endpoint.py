from fastapi.testclient import TestClient

from aegis.main import app


def test_agent_run_endpoint_completes_the_seeded_task():
    with TestClient(app) as client:
        response = client.post("/agent/run", json={"request": "Refund ticket TCK-4417."})
        assert response.status_code == 200
        body = response.json()
        assert body["stopped_reason"] == "final_answer"
        assert body["steps_taken"] == 3
        assert len(body["call_ids"]) == 3
