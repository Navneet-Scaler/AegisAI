"""Bearer token guard for the control plane.

Approvals, policy writes, and demo reset require this from the moment those
endpoints exist. Read endpoints stay public so the dashboard is viewable
without a token; the dashboard only sends this header when a human takes an
action. An unauthenticated approve endpoint is the first thing a reviewer of
a security-themed project would test, so this is not deferred to deployment.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from aegis.config import get_settings


async def require_demo_token(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.demo_token}"

    # hmac.compare_digest instead of `!=`: a plain string comparison short
    # circuits on the first mismatched byte, which leaks how many leading
    # characters of a guess were correct through response timing. The
    # demo token guards the one endpoint that can turn a held call into an
    # executed one, so it gets the same treatment real credential
    # comparisons do, even though it is a shared demo secret today.
    if authorization is None or not hmac.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token.",
        )
