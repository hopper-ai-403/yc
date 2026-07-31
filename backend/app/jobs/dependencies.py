"""Job feature FastAPI dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.repository import (
    AudioBatchRepository,
    AudioRepository,
    SqlAlchemyAudioBatchRepository,
    SqlAlchemyAudioRepository,
)
from app.config.settings import JobSettings, Settings, get_settings
from app.dependencies import get_db_session, get_redis
from app.infrastructure.redis.client import RedisClient
from app.infrastructure.redis.job_progress import JobProgressCache
from app.jobs.dispatcher import CeleryJobDispatcher, JobDispatcher
from app.jobs.repository import JobRepository, SqlAlchemyJobRepository
from app.jobs.service import JobService


def get_job_settings(settings: Settings = Depends(get_settings)) -> JobSettings:
    return settings.jobs


def get_job_repository(
    session: AsyncSession = Depends(get_db_session),
) -> JobRepository:
    return SqlAlchemyJobRepository(session)


def get_batch_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AudioBatchRepository:
    return SqlAlchemyAudioBatchRepository(session)


def get_audio_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AudioRepository:
    return SqlAlchemyAudioRepository(session)


def get_job_progress_cache(
    redis: RedisClient = Depends(get_redis),
    job_settings: JobSettings = Depends(get_job_settings),
) -> JobProgressCache:
    return JobProgressCache(redis, job_settings)


def get_job_dispatcher() -> JobDispatcher:
    return CeleryJobDispatcher()


def get_job_service(
    job_settings: JobSettings = Depends(get_job_settings),
    jobs: JobRepository = Depends(get_job_repository),
    batches: AudioBatchRepository = Depends(get_batch_repository),
    assets: AudioRepository = Depends(get_audio_repository),
    progress_cache: JobProgressCache = Depends(get_job_progress_cache),
    dispatcher: JobDispatcher = Depends(get_job_dispatcher),
) -> JobService:
    return JobService(
        settings=job_settings,
        jobs=jobs,
        batches=batches,
        assets=assets,
        progress_cache=progress_cache,
        dispatcher=dispatcher,
    )
