"""Public API keys for POST /v1/guard.

No external auth provider: keys are `aegis_live_<32 random chars>`, hashed
with SHA-256 before storage, shown in full exactly once at creation. Key
creation itself is rate limited per IP in process (no external service, and
no persistence needed for something this cheap to reset on a restart) so the
frictionless "no signup" path can't be used to mint unlimited keys.

Lifecycle (revoke, rotate, expire) exists because a credential with no way
to invalidate it is a real gap for a system whose entire pitch is being a
trust boundary: a leaked key otherwise stays valid forever. Revoking and
rotating both require presenting the key itself as the bearer token, the
same "prove you hold the credential" model Stripe and GitHub use for their
own key rotation flows, not a separate admin password.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from aegis.db import get_session
from aegis.models import ApiKey

KEY_PREFIX = "aegis_live_"
_TOKEN_BYTES = 24  # -> 32 url-safe base64 chars

KEY_CREATION_LIMIT = 3
KEY_CREATION_WINDOW_SECONDS = 3600

# In-process only, matching the rest of this API's "no external service"
# constraint. Resets on restart, which is an acceptable trade for a limit
# that exists to blunt casual abuse, not to be airtight.
_creation_attempts: dict[str, list[float]] = defaultdict(list)


def _hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def generate_raw_key() -> str:
    return f"{KEY_PREFIX}{secrets.token_urlsafe(_TOKEN_BYTES)}"


def check_creation_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    window_start = now - KEY_CREATION_WINDOW_SECONDS
    attempts = [t for t in _creation_attempts[client_ip] if t > window_start]
    if len(attempts) >= KEY_CREATION_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"No more than {KEY_CREATION_LIMIT} keys per IP per hour. "
                "Reuse the key you already have."
            ),
        )
    attempts.append(now)
    _creation_attempts[client_ip] = attempts


async def create_key(
    session: AsyncSession,
    *,
    owner_label: str = "anonymous",
    policy_id: str = "default",
    expires_in_days: int | None = None,
) -> tuple[ApiKey, str]:
    raw_key = generate_raw_key()
    expires_at = _now() + timedelta(days=expires_in_days) if expires_in_days else None
    row = ApiKey(
        id=str(uuid4()),
        key_hash=_hash(raw_key),
        owner_label=owner_label,
        policy_id=policy_id,
        expires_at=expires_at,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row, raw_key


async def _lookup_by_raw_key(session: AsyncSession, raw_key: str) -> ApiKey | None:
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == _hash(raw_key)))
    return result.scalar_one_or_none()


def _is_live(row: ApiKey | None) -> bool:
    if row is None or row.revoked_at is not None:
        return False
    if row.expires_at is not None:
        # SQLite drops tzinfo on round-trip even though the value was
        # written as UTC-aware; every datetime this table stores is UTC,
        # so a naive value read back is assumed to be UTC, not local time.
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= _now():
            return False
    return True


async def require_api_key(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ApiKey:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token. Mint one with POST /v1/keys.",
        )

    raw_key = authorization.removeprefix("Bearer ").strip()
    row = await _lookup_by_raw_key(session, raw_key)

    if not _is_live(row):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")

    row.request_count += 1
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def revoke_key(session: AsyncSession, *, raw_key: str) -> ApiKey:
    """Revoking requires presenting the key itself, the same "prove you hold
    the credential" bar as minting or rotating one. There is no separate
    admin path to revoke someone else's key."""
    row = await _lookup_by_raw_key(session, raw_key)
    if not _is_live(row):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")

    row.revoked_at = _now()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def rotate_key(session: AsyncSession, *, raw_key: str) -> tuple[ApiKey, str]:
    """Mints a replacement key carrying the old key's owner_label and
    policy_id, then revokes the old one. There is a brief window where both
    keys are simultaneously valid (the new one is committed before the old
    one is revoked) rather than a gap where neither works."""
    old_row = await _lookup_by_raw_key(session, raw_key)
    if not _is_live(old_row):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
    assert old_row is not None  # narrows the type for the rest of this function

    new_row, new_raw_key = await create_key(
        session, owner_label=old_row.owner_label, policy_id=old_row.policy_id
    )

    old_row.revoked_at = _now()
    session.add(old_row)
    await session.commit()

    return new_row, new_raw_key
