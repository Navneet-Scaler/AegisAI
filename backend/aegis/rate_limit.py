"""In-process rate limiting via `slowapi`. No external service, no paid
tier: this is the free-tier constraint the whole hosted API is built
under, not just a cost-saving shortcut.
"""

from __future__ import annotations

from slowapi import Limiter
from starlette.requests import Request


def _rate_limit_key(request: Request) -> str:
    """Keys by the raw bearer token so each API key gets its own budget,
    without needing a database lookup inside this synchronous callback.
    Falls back to the client IP for unauthenticated requests, such as
    POST /v1/keys itself, which has its own, separate limit in aegis.keys.
    """
    authorization = request.headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        return authorization
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_rate_limit_key)
