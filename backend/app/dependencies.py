"""Shared FastAPI dependencies.

Inject repositories, storage, settings, logger, services, and AI engines
via FastAPI Depends. Never instantiate them inside routes.
"""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.infrastructure.r2.client import CloudflareR2Storage
from app.infrastructure.redis.client import RedisClient, get_redis_client
from app.shared.database.session import async_session_factory
from app.shared.storage.provider import StorageProvider


def get_app_settings() -> Settings:
    """Provide application settings."""
    return get_settings()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session."""
    session_factory = async_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_storage(settings: Settings | None = None) -> StorageProvider:
    """Provide the configured StorageProvider implementation."""
    resolved = settings or get_settings()
    return CloudflareR2Storage(resolved.r2)


def get_redis(request: Request) -> RedisClient:
    """Provide the Redis client from application state when available."""
    redis_client: RedisClient | None = getattr(request.app.state, "redis", None)
    if redis_client is not None:
        return redis_client
    return get_redis_client()
