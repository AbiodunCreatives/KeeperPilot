"""Async engine and session management for the KeeperPilot database."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app.core.config import get_settings


def build_engine(database_url: str) -> AsyncEngine:
    """Create an async engine for the given SQLAlchemy database URL."""
    return create_async_engine(database_url, echo=False, pool_pre_ping=True)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to an engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


engine: AsyncEngine = build_engine(get_settings().database_url)
async_session_factory: async_sessionmaker[AsyncSession] = build_session_factory(engine)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        yield session
