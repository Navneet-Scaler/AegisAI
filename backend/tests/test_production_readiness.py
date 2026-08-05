"""SQLite does not survive more than one running instance, and the held-call
approval flow depends on durable, consistent database state across
restarts. A production deployment pointed at SQLite is a silent multi-
instance failure waiting to happen; refusing to start is the same
fail-closed instinct the rules-file check already applies to policy,
applied here to the data layer."""

import pytest

from aegis.config import Settings


def test_is_sqlite_detects_the_default_local_url():
    settings = Settings(database_url="sqlite+aiosqlite:///./aegis.db")
    assert settings.is_sqlite is True


def test_is_sqlite_is_false_for_postgres():
    settings = Settings(database_url="postgresql+asyncpg://user:pass@host/db")
    assert settings.is_sqlite is False


async def test_app_refuses_to_start_on_sqlite_in_production(monkeypatch):
    monkeypatch.setenv("AEGIS_ENVIRONMENT", "production")
    monkeypatch.setenv("AEGIS_DATABASE_URL", "sqlite+aiosqlite:///./aegis.db")

    from aegis.config import get_settings

    get_settings.cache_clear()
    try:
        import importlib

        import aegis.main as main_module

        importlib.reload(main_module)

        from fastapi.testclient import TestClient

        with pytest.raises(RuntimeError, match="SQLite"):
            with TestClient(main_module.app):
                pass
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        import importlib

        import aegis.main as main_module

        importlib.reload(main_module)
