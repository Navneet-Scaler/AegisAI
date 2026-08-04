import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.db import get_sessionmaker, init_db


@pytest.fixture(autouse=True)
async def _prepare_db():
    await init_db()
    yield


@pytest.fixture
async def db_session() -> AsyncSession:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session
