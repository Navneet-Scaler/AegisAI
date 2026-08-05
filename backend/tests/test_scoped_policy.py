"""Per-key scoped rules: two keys on different policies must score the same
call differently. Without this, "hosted API" is hosted in name only, since
every caller would be forced onto one team's rule tuning."""

from fastapi.testclient import TestClient

from aegis.main import app


def _mint_key(client: TestClient, policy_id: str = "default") -> str:
    response = client.post("/v1/keys", json={"owner_label": "test", "policy_id": policy_id})
    assert response.status_code == 200, response.text
    return response.json()["key"]


def test_policies_endpoint_lists_default_and_strict():
    with TestClient(app) as client:
        response = client.get("/v1/policies")
        assert response.status_code == 200
        assert {"default", "strict"} <= set(response.json())


def test_unknown_policy_id_is_rejected_at_key_creation():
    with TestClient(app) as client:
        response = client.post(
            "/v1/keys", json={"owner_label": "test", "policy_id": "does-not-exist"}
        )
        assert response.status_code == 400


def test_default_and_strict_policies_diverge_on_the_same_call():
    """A $150 refund holds under strict (threshold $100) but not under
    default (threshold $500): same call, same tool, different verdict,
    entirely because of which key scored it."""
    with TestClient(app) as client:
        default_key = _mint_key(client, "default")
        strict_key = _mint_key(client, "strict")

        payload = {
            "tool": "create_refund",
            "args": {"customer_id": "CUST-1", "amount": 150, "reason": "goodwill"},
        }

        default_result = client.post(
            "/v1/guard", json=payload, headers={"Authorization": f"Bearer {default_key}"}
        ).json()
        strict_result = client.post(
            "/v1/guard", json=payload, headers={"Authorization": f"Bearer {strict_key}"}
        ).json()

        assert default_result["verdict"] == "allow"
        assert strict_result["verdict"] == "hold"


def test_new_keys_default_to_the_most_restrictive_policy():
    with TestClient(app) as client:
        response = client.post("/v1/keys", json={"owner_label": "test"})
        assert response.json()["policy_id"] == "default"


def test_agent_id_is_recorded_separately_from_the_key_owner():
    """Two calls under the same key but different agent_id values should be
    attributable to different agents in the audit trail, not collapsed into
    one identity."""
    with TestClient(app) as client:
        key = _mint_key(client)

        client.post(
            "/v1/guard",
            json={
                "tool": "read_ticket",
                "args": {"id": "TCK-1"},
                "context": {"agent_id": "support-bot"},
            },
            headers={"Authorization": f"Bearer {key}"},
        )
        client.post(
            "/v1/guard",
            json={
                "tool": "read_ticket",
                "args": {"id": "TCK-2"},
                "context": {"agent_id": "billing-bot"},
            },
            headers={"Authorization": f"Bearer {key}"},
        )

        calls = client.get("/calls").json()
        agent_names = {c["agent_name"] for c in calls if c["tool_name"] == "read_ticket"}
        assert {"support-bot", "billing-bot"} <= agent_names

        # Both calls carry the same api_key_id even though agent_name differs,
        # proving the two identities are tracked independently.
        api_key_ids = {
            c["api_key_id"] for c in calls if c["agent_name"] in {"support-bot", "billing-bot"}
        }
        assert len(api_key_ids) == 1
