"""Redis client with health-check support."""

from functools import lru_cache

import redis.asyncio as aioredis
from typing_extensions import Self

from app.config.settings import RedisSettings, get_settings


class RedisClient:
    """Thin async Redis wrapper used for health checks and future caching."""

    def __init__(self, settings: RedisSettings) -> None:
        self._settings = settings
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Establish the Redis connection."""
        if self._client is None:
            self._client = aioredis.from_url(
                self._settings.url,
                encoding="utf-8",
                decode_responses=True,
                health_check_interval=self._settings.health_check_interval,
            )

    async def disconnect(self) -> None:
        """Close the Redis connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        """Return the underlying Redis client."""
        if self._client is None:
            raise RuntimeError("Redis client is not connected")
        return self._client

    async def health_check(self) -> bool:
        """Return True if Redis responds to PING."""
        try:
            if self._client is None:
                await self.connect()
            result = await self.client.ping()
            return bool(result)
        except Exception:
            return False

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.disconnect()


@lru_cache
def get_redis_client() -> RedisClient:
    """Return a cached RedisClient instance."""
    return RedisClient(get_settings().redis)
