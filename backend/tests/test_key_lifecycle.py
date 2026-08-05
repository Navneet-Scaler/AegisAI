"""API key rotation, revocation, and expiry. A credential with no way to
invalidate it is a real gap for a system whose whole pitch is being a trust
boundary: a leaked key would otherwise stay valid forever."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import select

from aegis.db import get_sessionmaker
from aegis.main import app
from aegis.models import ApiKey


def _mint_key(client: TestClient) -> str:
    response = client.post("/v1/keys", json={"owner_label": "test"})
    assert response.status_code == 200
    return response.json()["key"]


def test_revoked_key_is_rejected_immediately():
    with TestClient(app) as client:
        key = _mint_key(client)

        revoke = client.post("/v1/keys/revoke", headers={"Authorization": f"Bearer {key}"})
        assert revoke.status_code == 200
        assert revoke.json()["revoked_at"]

        guard = client.post(
            "/v1/guard",
            json={"tool": "read_ticket", "args": {"id": "TCK-1"}},
            headers={"Authorization": f"Bearer {key}"},
        )
        assert guard.status_code == 401


def test_revoking_requires_the_key_itself():
    with TestClient(app) as client:
        response = client.post("/v1/keys/revoke")
        assert response.status_code == 401

        response = client.post(
            "/v1/keys/revoke", headers={"Authorization": "Bearer not-a-real-key"}
        )
        assert response.status_code == 401


def test_rotate_returns_a_new_key_and_invalidates_the_old_one():
    with TestClient(app) as client:
        old_key = _mint_key(client)

        rotate = client.post("/v1/keys/rotate", headers={"Authorization": f"Bearer {old_key}"})
        assert rotate.status_code == 200
        new_key = rotate.json()["key"]
        assert new_key != old_key

        old_call = client.post(
            "/v1/guard",
            json={"tool": "read_ticket", "args": {"id": "TCK-1"}},
            headers={"Authorization": f"Bearer {old_key}"},
        )
        assert old_call.status_code == 401

        new_call = client.post(
            "/v1/guard",
            json={"tool": "read_ticket", "args": {"id": "TCK-1"}},
            headers={"Authorization": f"Bearer {new_key}"},
        )
        assert new_call.status_code == 200


def test_rotated_key_keeps_the_same_owner_and_policy():
    with TestClient(app) as client:
        create = client.post(
            "/v1/keys", json={"owner_label": "acme-billing", "policy_id": "strict"}
        )
        old_key = create.json()["key"]

        rotate = client.post("/v1/keys/rotate", headers={"Authorization": f"Bearer {old_key}"})
        body = rotate.json()
        assert body["owner_label"] == "acme-billing"
        assert body["policy_id"] == "strict"


async def test_expired_key_is_rejected(db_session):
    """Set expires_at in the past directly, the same as if expires_in_days
    had elapsed, and confirm the key stops working without needing to wait."""
    with TestClient(app) as client:
        create = client.post("/v1/keys", json={"owner_label": "test", "expires_in_days": 30})
        key_id = create.json()["key_id"]
        raw_key = create.json()["key"]

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        result = await session.execute(select(ApiKey).where(ApiKey.id == key_id))
        row = result.scalar_one()
        row.expires_at = datetime.now(UTC) - timedelta(days=1)
        session.add(row)
        await session.commit()

    with TestClient(app) as client:
        response = client.post(
            "/v1/guard",
            json={"tool": "read_ticket", "args": {"id": "TCK-1"}},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert response.status_code == 401
