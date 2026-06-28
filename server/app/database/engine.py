"""Async SQLAlchemy engine setup."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from server.app.config.settings import Settings, get_settings


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    loaded_settings = settings or get_settings()
    return create_async_engine(
        loaded_settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


engine = create_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

