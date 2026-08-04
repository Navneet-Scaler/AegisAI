import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.db import get_sessionmaker, init_db


@pytest.fixture(autouse=True)
async def _prepare_db():
    await init_db()
    yield


@pytest.fixture(autouse=True)
def _reset_key_creation_rate_limit():
    """The in-process, per-IP key creation limiter in aegis.keys is a
    module-level dict by design, no external store for something this
    cheap to reset on a restart. In the test suite every request comes
    from the same TestClient host, so without a reset here, tests would
    trip each other's rate limit rather than testing their own behaviour."""
    import aegis.keys as keys_module

    keys_module._creation_attempts.clear()
    yield


@pytest.fixture
async def db_session() -> AsyncSession:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session
