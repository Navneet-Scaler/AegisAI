from fastapi.testclient import TestClient

from aegis.main import app

client = TestClient(app)


def test_agent_run_endpoint_completes_the_seeded_task():
    response = client.post("/agent/run", json={"request": "Refund ticket TCK-4417."})
    assert response.status_code == 200
    body = response.json()
    assert body["stopped_reason"] == "final_answer"
    assert body["steps_taken"] == 3
