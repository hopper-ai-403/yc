"""Async SQLAlchemy engine and session management."""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Create and cache the async SQLAlchemy engine."""
    settings = get_settings()
    return create_async_engine(
        settings.database.url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=settings.database.pool_recycle,
        echo=settings.database.echo,
        pool_pre_ping=True,
    )


@lru_cache
def async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create and cache the async session factory."""
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    session_factory = async_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
