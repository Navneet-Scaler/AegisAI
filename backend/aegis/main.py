"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from aegis.aegisai.rules import list_policy_ids, load_rules
from aegis.api.agent import router as agent_router
from aegis.api.analytics import router as analytics_router
from aegis.api.calls import router as calls_router
from aegis.api.demo import router as demo_router
from aegis.api.policy import router as policy_router
from aegis.api.stream import router as stream_router
from aegis.api.v1 import router as v1_router
from aegis.config import get_settings
from aegis.db import init_db
from aegis.rate_limit import limiter

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
        if settings.environment == "production":
            raise
    yield


app = FastAPI(
    title="AegisAI",
    description=(
        "Score an AI agent's proposed tool call before it executes. "
        "POST /v1/guard runs a rule engine, an online pattern model, and an LLM "
        "judge, and returns allow, hold, or block. Mint a key at POST /v1/keys, "
        "no signup required."
    ),
    version="0.7.0",
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
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "llm_mode": settings.llm_mode,
    }
