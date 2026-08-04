"""Runtime configuration.

Defaults are chosen so that a clean clone with no environment file runs the full
demo offline: replay LLM mode, local SQLite, and a restrictive CORS allowlist.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AEGIS_", env_file=".env", extra="ignore")

    environment: Literal["local", "production"] = "local"

    # Storage. SQLite locally, Postgres on the deployed backend.
    database_url: str = "sqlite+aiosqlite:///./aegis.db"

    # CORS is an explicit allowlist from the first commit. There is no permissive
    # default that we remember to tighten later.
    cors_origins: str = "http://localhost:3000"

    # Shared bearer token guarding the control plane: approvals, policy writes,
    # and demo reset. Read endpoints stay public so the dashboard is viewable.
    demo_token: str = "aegis-local-dev-token"

    # "replay" serves recorded judge verdicts and needs no API key. "live" calls
    # Gemini. "mock" uses scripted responses for tests.
    llm_mode: Literal["replay", "live", "mock"] = "replay"
    gemini_api_key: str = ""

    # How long a held call waits for a human before it is refused.
    approval_timeout_seconds: int = 120

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
