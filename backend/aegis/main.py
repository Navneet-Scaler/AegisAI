"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegis.aegisai.rules import load_rules
from aegis.api.agent import router as agent_router
from aegis.api.analytics import router as analytics_router
from aegis.api.calls import router as calls_router
from aegis.api.demo import router as demo_router
from aegis.api.stream import router as stream_router
from aegis.config import get_settings
from aegis.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    # A rules file that fails to parse is a fail-closed condition. In
    # production the app refuses to start rather than serving traffic that
    # would fall back to a per-request hold on every single call.
    try:
        load_rules()
    except Exception:
        if settings.environment == "production":
            raise
    yield


app = FastAPI(
    title="AegisAI",
    description="An architectural firewall for AI agents.",
    version="0.1.0",
    lifespan=lifespan,
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
app.include_router(stream_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "llm_mode": settings.llm_mode,
    }
