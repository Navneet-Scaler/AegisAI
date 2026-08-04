"""Bearer token guard for the control plane.

Approvals, policy writes, and demo reset require this from the moment those
endpoints exist. Read endpoints stay public so the dashboard is viewable
without a token; the dashboard only sends this header when a human takes an
action. An unauthenticated approve endpoint is the first thing a reviewer of
a security-themed project would test, so this is not deferred to deployment.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from aegis.config import get_settings


async def require_demo_token(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.demo_token}"

    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token.",
        )
