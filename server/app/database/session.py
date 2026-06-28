"""Database session dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.app.database.engine import AsyncSessionLocal


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for request handling."""
    async with AsyncSessionLocal() as session:
        yield session


def make_session_dependency(
    sessionmaker: async_sessionmaker[AsyncSession],
):
    """Create a FastAPI dependency from an async sessionmaker."""

    async def dependency() -> AsyncGenerator[AsyncSession, None]:
        async with sessionmaker() as session:
            yield session

    return dependency

