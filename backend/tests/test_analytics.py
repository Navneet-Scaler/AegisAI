from fastapi.testclient import TestClient

from aegis.main import app


def test_model_snapshot_exposes_feature_names_and_weights():
    with TestClient(app) as client:
        response = client.get("/analytics/model")
        assert response.status_code == 200
        body = response.json()
        assert len(body["weights"]) == len(body["feature_names"])
        assert body["update_count"] >= 0


def test_verdict_and_tool_breakdowns_reflect_a_run():
    with TestClient(app) as client:
        client.post("/agent/run", json={"request": "Refund ticket TCK-4417."})

        verdicts = client.get("/analytics/verdicts").json()
        assert sum(row["count"] for row in verdicts) >= 3

        tools = client.get("/analytics/tools").json()
        names = {row["tool_name"] for row in tools}
        assert {"read_ticket", "search_customers", "create_refund"} <= names
