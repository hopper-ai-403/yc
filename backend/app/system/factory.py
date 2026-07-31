"""Factory for SystemService outside FastAPI DI."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.audio.repository import (
    SqlAlchemyAudioBatchRepository,
    SqlAlchemyAudioRepository,
)
from app.config.settings import Settings, get_settings
from app.infrastructure.r2.client import CloudflareR2Storage
from app.infrastructure.redis.client import RedisClient, get_redis_client
from app.infrastructure.redis.job_progress import JobProgressCache
from app.jobs.repository import SqlAlchemyJobRepository
from app.prediction.repository import SqlAlchemyPredictionRepository
from app.shared.database.session import get_engine
from app.shared.storage.provider import StorageProvider
from app.system.benchmark import BenchmarkRunner
from app.system.service import SystemService


def build_system_service(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
    storage: StorageProvider | None = None,
    redis_client: RedisClient | None = None,
    engine: AsyncEngine | None = None,
) -> SystemService:
    """Construct SystemService with concrete infrastructure collaborators."""
    resolved = settings or get_settings()
    redis = redis_client or get_redis_client()
    return SystemService(
        settings=resolved,
        engine=engine or get_engine(),
        redis_client=redis,
        storage=storage or CloudflareR2Storage(resolved.r2),
        progress_cache=JobProgressCache(redis, resolved.jobs),
        benchmark=BenchmarkRunner(
            batches=SqlAlchemyAudioBatchRepository(session),
            assets=SqlAlchemyAudioRepository(session),
            predictions=SqlAlchemyPredictionRepository(session),
            jobs=SqlAlchemyJobRepository(session),
        ),
    )
