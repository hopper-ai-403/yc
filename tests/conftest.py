"""Shared pytest fixtures."""

import asyncio
import os
import sys
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("APP_ENVIRONMENT", "test")
os.environ.setdefault("LOGGING_JSON_LOGS", "false")
os.environ.setdefault("LOGGING_LEVEL", "WARNING")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://aip:aip@localhost:5432/aip_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Return a FastAPI TestClient with Redis lifespan mocked."""
    from app.config.settings import get_settings
    from app.infrastructure.redis.client import get_redis_client
    from app.main import create_application
    from app.shared.database.session import async_session_factory, get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    async_session_factory.cache_clear()
    get_redis_client.cache_clear()

    application = create_application()

    with (
        patch(
            "app.main.get_redis_client",
        ) as mock_get_redis,
    ):
        redis_mock = AsyncMock()
        redis_mock.connect = AsyncMock()
        redis_mock.disconnect = AsyncMock()
        redis_mock.health_check = AsyncMock(return_value=True)
        mock_get_redis.return_value = redis_mock

        with TestClient(application) as test_client:
            yield test_client

    get_settings.cache_clear()
    get_engine.cache_clear()
    async_session_factory.cache_clear()
    get_redis_client.cache_clear()
