"""Factory helpers for constructing JobService outside FastAPI DI."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.repository import (
    SqlAlchemyAudioBatchRepository,
    SqlAlchemyAudioRepository,
)
from app.config.settings import JobSettings, get_settings
from app.infrastructure.redis.client import RedisClient, get_redis_client
from app.infrastructure.redis.job_progress import JobProgressCache
from app.jobs.dispatcher import CeleryJobDispatcher, JobDispatcher
from app.jobs.repository import SqlAlchemyJobRepository
from app.jobs.service import JobService


def build_job_service(
    session: AsyncSession,
    *,
    redis: RedisClient | None = None,
    dispatcher: JobDispatcher | None = None,
    settings: JobSettings | None = None,
) -> JobService:
    """Construct a JobService with concrete infrastructure collaborators."""
    job_settings = settings or get_settings().jobs
    redis_client = redis or get_redis_client()
    return JobService(
        settings=job_settings,
        jobs=SqlAlchemyJobRepository(session),
        batches=SqlAlchemyAudioBatchRepository(session),
        assets=SqlAlchemyAudioRepository(session),
        progress_cache=JobProgressCache(redis_client, job_settings),
        dispatcher=dispatcher or CeleryJobDispatcher(),
    )
