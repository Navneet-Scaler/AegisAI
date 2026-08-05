"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from aegis.aegisai.core import reconcile_orphaned_executions
from aegis.aegisai.rules import list_policy_ids, load_rules
from aegis.api.agent import router as agent_router
from aegis.api.analytics import router as analytics_router
from aegis.api.calls import router as calls_router
from aegis.api.demo import router as demo_router
from aegis.api.policy import router as policy_router
from aegis.api.stream import router as stream_router
from aegis.api.v1 import router as v1_router
from aegis.config import get_settings
from aegis.db import get_sessionmaker, init_db
from aegis.rate_limit import limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("aegisai")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SQLite is a single-writer, single-file store: it does not survive
    # multiple app instances behind a load balancer, and the held-call
    # approval flow depends on database state being consistent and durable
    # across restarts. That is fine for local dev, and refusing to start on
    # SQLite in production is the same fail-closed instinct as the rules
    # file check below, applied to the data layer instead of the policy
    # layer: better to refuse to start than to serve traffic against a
    # store that silently breaks the moment there is a second instance.
    if settings.environment == "production" and settings.is_sqlite:
        raise RuntimeError(
            "AEGIS_DATABASE_URL is SQLite in a production environment. "
            "Point it at Postgres (postgresql+asyncpg://...) before deploying; "
            "SQLite does not survive more than one running instance."
        )

    # The demo token is a shared secret meant for the public demo, printed
    # in this repo's own README. Shipping it unchanged to production would
    # mean the approve/block endpoint is effectively unauthenticated; the
    # same fail-closed instinct as the SQLite check above, applied to auth
    # instead of storage.
    if settings.environment == "production" and settings.demo_token == "aegis-local-dev-token":
        raise RuntimeError(
            "AEGIS_DEMO_TOKEN is still the default demo value in a production "
            "environment. Set it to a real secret before deploying."
        )

    await init_db()

    # A policy file that fails to parse is a fail-closed condition. In
    # production the app refuses to start rather than serving traffic that
    # would fall back to a per-request hold on every single call. Every
    # policy on disk is validated, not just "default": a key scoped to a
    # broken policy must never be discovered at request time.
    try:
        for policy_id in list_policy_ids() or ["default"]:
            load_rules(policy_id)
    except Exception:
        logger.exception("Failed to load rules for at least one policy at startup.")
        if settings.environment == "production":
            raise

    # slowapi's default limiter keeps its counters in process memory. On a
    # serverless deployment (the README's primary path via Vercel) every
    # cold function invocation starts a fresh process, so those counters
    # reset with it: the documented per-key and per-IP limits do not
    # actually hold there. Long-lived single-instance deployments (Railway,
    # Docker Compose) are unaffected. Logged once at startup rather than
    # silently relied on.
    if settings.environment == "production":
        logger.warning(
            "Rate limiting is in-process (slowapi). On a serverless deployment "
            "target, per-instance counters reset on every cold start and the "
            "documented limits are not enforced across instances. See README."
        )

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        reconciled = await reconcile_orphaned_executions(session)
        if reconciled:
            logger.warning(
                "Reconciled %d call(s) that executed but were never marked "
                "resolved, likely from a crash between those two commits: %s",
                len(reconciled),
                reconciled,
            )

    yield


app = FastAPI(
    title="AegisAI",
    description=(
        "Score an AI agent's proposed tool call before it executes. "
        "POST /v1/guard runs a rule engine, an online pattern model, and an LLM "
        "judge, and returns allow, hold, or block. Mint a key at POST /v1/keys, "
        "no signup required."
    ),
    version="0.8.0",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limited", "detail": str(exc.detail)},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(agent_router)
app.include_router(analytics_router)
app.include_router(calls_router)
app.include_router(demo_router)
app.include_router(policy_router)
app.include_router(stream_router)
app.include_router(v1_router)


@app.get("/health")
async def health() -> JSONResponse:
    """A previous version of this endpoint returned a hardcoded "ok" no
    matter what: it would say healthy while the database was unreachable
    or, in live mode, while no judge credential was configured at all,
    exactly the kind of silent failure this project's own fail-closed
    design elsewhere argues against. This one actually checks."""
    from sqlalchemy import text

    checks: dict[str, str] = {}
    healthy = True

    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        healthy = False
        checks["database"] = f"unreachable: {exc}"
        logger.error("Health check: database unreachable: %s", exc)

    if settings.llm_mode == "live":
        checks["judge"] = "ok" if settings.gemini_api_key else "no api key configured"
        if not settings.gemini_api_key:
            healthy = False
            logger.error("Health check: AEGIS_LLM_MODE=live with no Gemini API key set.")
    else:
        checks["judge"] = f"{settings.llm_mode} mode, no external dependency"

    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "degraded",
            "environment": settings.environment,
            "llm_mode": settings.llm_mode,
            "checks": checks,
        },
    )
