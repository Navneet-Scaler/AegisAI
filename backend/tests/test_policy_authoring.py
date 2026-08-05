"""Rule authoring: save a draft, dry-run it against history before
activating, activate it, and confirm rollback (activating an older version
again) actually changes what a call scores against."""

from fastapi.testclient import TestClient

from aegis.config import get_settings
from aegis.main import app


def _mint_key(client: TestClient, policy_id: str = "default") -> str:
    response = client.post("/v1/keys", json={"owner_label": "test", "policy_id": policy_id})
    assert response.status_code == 200, response.text
    return response.json()["key"]


def test_unedited_policy_reads_from_the_seed_yaml():
    with TestClient(app) as client:
        response = client.get("/v1/policies/default/rules")
        assert response.status_code == 200
        body = response.json()
        assert body["source"] == "seed"
        assert any(r["id"] == "destructive-delete" for r in body["rules"])


def test_unknown_policy_id_returns_404():
    with TestClient(app) as client:
        response = client.get("/v1/policies/does-not-exist/rules")
        assert response.status_code == 404


def test_draft_and_activate_require_the_demo_token():
    with TestClient(app) as client:
        response = client.post("/v1/policies/default/draft", json={"rules": []})
        assert response.status_code == 401


def test_draft_rejects_a_malformed_rule_set():
    settings = get_settings()
    token = f"Bearer {settings.demo_token}"
    with TestClient(app) as client:
        response = client.post(
            "/v1/policies/default/draft",
            json={"rules": [{"no_id": True}]},
            headers={"Authorization": token},
        )
        assert response.status_code == 400


def test_dry_run_reports_no_change_for_the_current_policy_against_itself():
    with TestClient(app) as client:
        current = client.get("/v1/policies/default/rules").json()["rules"]
        response = client.post("/v1/policies/default/dry-run", json={"rules": current})
        assert response.status_code == 200
        # Sample size may be 0 in a fresh database, that's fine, the point
        # is dry-running the unchanged policy against itself never reports
        # a call flipping verdict.
        assert response.json()["would_change"] == 0


def test_dry_run_against_a_tighter_policy_shows_the_blast_radius():
    """Score a $150 refund under default (allow), then dry-run the strict
    policy's threshold against that same history and confirm it would flip."""
    settings = get_settings()
    token = f"Bearer {settings.demo_token}"

    with TestClient(app) as client:
        key = _mint_key(client, "default")
        client.post(
            "/v1/guard",
            json={
                "tool": "create_refund",
                "args": {"customer_id": "C1", "amount": 150, "reason": "goodwill"},
            },
            headers={"Authorization": f"Bearer {key}"},
        )

        strict_rules = client.get("/v1/policies/strict/rules").json()["rules"]
        dry_run = client.post("/v1/policies/default/dry-run", json={"rules": strict_rules}).json()

        assert dry_run["sample_size"] >= 1
        assert dry_run["would_change"] >= 1
        assert dry_run["newly_forced_hold"] >= 1

        # Confirm the token requirement is still enforced for the write
        # side even though this test only exercised the read side.
        response = client.post("/v1/policies/default/draft", json={"rules": strict_rules})
        assert response.status_code == 401
        response = client.post(
            "/v1/policies/default/draft",
            json={"rules": strict_rules, "description": "tighten refunds"},
            headers={"Authorization": token},
        )
        assert response.status_code == 200


def test_saving_a_draft_does_not_activate_it():
    settings = get_settings()
    token = f"Bearer {settings.demo_token}"
    with TestClient(app) as client:
        draft = client.post(
            "/v1/policies/default/draft",
            json={"rules": [{"id": "noop", "match": {"tool_in": ["nothing"]}, "score": 0.1}]},
            headers={"Authorization": token},
        ).json()
        assert draft["is_active"] is False

        # The active rules are unaffected: still the seed policy.
        active = client.get("/v1/policies/default/rules").json()
        assert active["source"] == "seed"


def test_activating_a_draft_changes_what_new_calls_score_against():
    settings = get_settings()
    token = f"Bearer {settings.demo_token}"
    with TestClient(app) as client:
        # A permissive policy that never forces anything, proving
        # activation really did take effect rather than the default
        # destructive-delete rule still applying underneath.
        permissive_rules = [
            {"id": "noop", "match": {"tool_in": ["nothing-matches-this"]}, "score": 0.1}
        ]
        draft = client.post(
            "/v1/policies/default/draft",
            json={"rules": permissive_rules, "description": "permissive test policy"},
            headers={"Authorization": token},
        ).json()

        activated = client.post(
            f"/v1/policies/default/versions/{draft['id']}/activate",
            headers={"Authorization": token},
        )
        assert activated.status_code == 200
        assert activated.json()["is_active"] is True

        active = client.get("/v1/policies/default/rules").json()
        assert active["source"] == "saved"
        assert active["rules"] == permissive_rules

        key = _mint_key(client, "default")
        result = client.post(
            "/v1/guard",
            json={"tool": "delete_customer", "args": {"customer_id": "C1"}},
            headers={"Authorization": f"Bearer {key}"},
        ).json()
        # Under the seed policy this always forces at least hold. Under the
        # permissive activated policy, nothing matches, so the rule layer
        # no longer forces anything.
        assert result["layers"]["rule"] == 0.1


def test_rollback_is_just_activating_an_older_version_again():
    settings = get_settings()
    token = f"Bearer {settings.demo_token}"
    with TestClient(app) as client:
        seed_rules = client.get("/v1/policies/default/rules").json()["rules"]

        # Save the seed rules as v1 explicitly, then a permissive v2.
        v1 = client.post(
            "/v1/policies/default/draft",
            json={"rules": seed_rules, "description": "v1: same as seed"},
            headers={"Authorization": token},
        ).json()
        client.post(
            f"/v1/policies/default/versions/{v1['id']}/activate",
            headers={"Authorization": token},
        )

        v2_rules = [{"id": "noop", "match": {"tool_in": ["nothing"]}, "score": 0.1}]
        v2 = client.post(
            "/v1/policies/default/draft",
            json={"rules": v2_rules, "description": "v2: permissive"},
            headers={"Authorization": token},
        ).json()
        client.post(
            f"/v1/policies/default/versions/{v2['id']}/activate",
            headers={"Authorization": token},
        )
        assert client.get("/v1/policies/default/rules").json()["rules"] == v2_rules

        # Roll back: activate v1 again.
        rollback = client.post(
            f"/v1/policies/default/versions/{v1['id']}/activate",
            headers={"Authorization": token},
        )
        assert rollback.status_code == 200
        assert client.get("/v1/policies/default/rules").json()["rules"] == seed_rules

        versions = client.get("/v1/policies/default/versions").json()
        active_ids = [v["id"] for v in versions if v["is_active"]]
        assert active_ids == [v1["id"]]
