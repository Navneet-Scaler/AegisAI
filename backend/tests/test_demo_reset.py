from fastapi.testclient import TestClient

from aegis.config import get_settings
from aegis.main import app


def test_demo_reset_requires_a_token():
    with TestClient(app) as client:
        response = client.post("/demo/reset")
        assert response.status_code == 401


def test_demo_reset_clears_the_call_log():
    settings = get_settings()
    with TestClient(app) as client:
        client.post("/agent/run", json={"request": "Refund ticket TCK-4417."})
        assert len(client.get("/calls").json()) > 0

        response = client.post(
            "/demo/reset", headers={"Authorization": f"Bearer {settings.demo_token}"}
        )
        assert response.status_code == 200
        assert client.get("/calls").json() == []
