"""Public API keys for POST /v1/guard.

No external auth provider: keys are `aegis_live_<32 random chars>`, hashed
with SHA-256 before storage, shown in full exactly once at creation. Key
creation itself is rate limited per IP in process (no external service, and
no persistence needed for something this cheap to reset on a restart) so the
frictionless "no signup" path can't be used to mint unlimited keys.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict
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
    session: AsyncSession, *, owner_label: str = "anonymous"
) -> tuple[ApiKey, str]:
    raw_key = generate_raw_key()
    row = ApiKey(id=str(uuid4()), key_hash=_hash(raw_key), owner_label=owner_label)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row, raw_key


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
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == _hash(raw_key)))
    row = result.scalar_one_or_none()

    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")

    row.request_count += 1
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
