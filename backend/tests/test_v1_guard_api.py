"""POST /v1/guard and POST /v1/keys: the public, hosted surface. Any agent,
in any language, is meant to reach this without ever importing this repo's
Python package, so these tests go through the real HTTP routes exactly as
an external caller would, not through internal functions directly."""

from fastapi.testclient import TestClient

from aegis.main import app


def _mint_key(client: TestClient, owner_label: str = "test-suite") -> str:
    response = client.post("/v1/keys", json={"owner_label": owner_label})
    assert response.status_code == 200
    return response.json()["key"]


def test_guard_without_a_key_is_rejected():
    with TestClient(app) as client:
        response = client.post("/v1/guard", json={"tool": "read_ticket", "args": {}})
        assert response.status_code == 401


def test_guard_with_an_invalid_key_is_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/v1/guard",
            json={"tool": "read_ticket", "args": {}},
            headers={"Authorization": "Bearer not-a-real-key"},
        )
        assert response.status_code == 401


def test_key_creation_returns_a_usable_key():
    with TestClient(app) as client:
        response = client.post("/v1/keys", json={"owner_label": "acme"})
        assert response.status_code == 200
        body = response.json()
        assert body["key"].startswith("aegis_live_")
        assert body["owner_label"] == "acme"


def test_key_creation_is_rate_limited_per_ip():
    with TestClient(app) as client:
        statuses = [client.post("/v1/keys", json={}).status_code for _ in range(5)]
        assert statuses.count(429) > 0, "expected at least one 429 after repeated key creation"


def test_guard_matches_the_documented_response_shape():
    with TestClient(app) as client:
        key = _mint_key(client)
        response = client.post(
            "/v1/guard",
            json={
                "tool": "delete_customer",
                "args": {"customer_id": "8842"},
                "context": {
                    "user_request": "clean up test accounts",
                    "history": [{"role": "user", "content": "clean up test accounts"}],
                },
            },
            headers={"Authorization": f"Bearer {key}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["verdict"] in {"allow", "hold", "block"}
        assert {"rule", "pattern", "judge"} <= body["layers"].keys()
        assert "call_id" in body


def test_guard_holds_a_destructive_delete_regardless_of_the_other_layers():
    """destructive-delete in seed/rules.yaml forces at least hold for any
    delete_customer call, external caller or not."""
    with TestClient(app) as client:
        key = _mint_key(client)
        response = client.post(
            "/v1/guard",
            json={"tool": "delete_customer", "args": {"customer_ids": ["CUST-1"]}},
            headers={"Authorization": f"Bearer {key}"},
        )
        assert response.status_code == 200
        assert response.json()["verdict"] in {"hold", "block"}


def test_guard_scores_an_unregistered_external_tool_without_crashing():
    """An external caller's tool name will not be in AegisAI's own CRM
    registry. That must not be a 500, it should score with the moderate
    external default and return normally."""
    with TestClient(app) as client:
        key = _mint_key(client)
        response = client.post(
            "/v1/guard",
            json={"tool": "wire_transfer", "args": {"amount": 10}},
            headers={"Authorization": f"Bearer {key}"},
        )
        assert response.status_code == 200
        assert response.json()["verdict"] in {"allow", "hold", "block"}


def test_docs_and_redoc_are_public():
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.get("/openapi.json").status_code == 200
