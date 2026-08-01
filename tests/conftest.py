"""Shared pytest fixtures."""

import os

os.environ.setdefault("KEEPERHUB_MOCK", "true")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from database.models import Base


@pytest.fixture
async def db_engine():
    """In-memory SQLite engine with a shared connection pool.

    `StaticPool` + a single connection is required so every async session in a
    test talks to the same in-memory database.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def api_client(db_engine):
    """ASGI test client with the app's DB dependency swapped for the test DB."""
    import httpx
    from httpx import ASGITransport

    from backend.app.main import app
    from database.session import get_db

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
