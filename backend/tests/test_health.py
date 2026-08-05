from fastapi.testclient import TestClient

from aegis.main import app

client = TestClient(app)


def test_health_reports_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


def test_cors_is_not_wildcard():
    """A firewall project must never ship a permissive CORS default."""
    from aegis.config import get_settings

    assert "*" not in get_settings().cors_origin_list
