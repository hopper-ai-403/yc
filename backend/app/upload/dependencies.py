"""Upload feature FastAPI dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.repository import (
    AudioBatchRepository,
    AudioRepository,
    SqlAlchemyAudioBatchRepository,
    SqlAlchemyAudioRepository,
)
from app.auth.repository import SqlAlchemyUserRepository, UserRepository
from app.config.settings import Settings, UploadSettings, get_settings
from app.dependencies import get_db_session, get_storage
from app.jobs.repository import JobRepository, SqlAlchemyJobRepository
from app.shared.storage.provider import StorageProvider
from app.upload.service import UploadService


def get_upload_settings(
    settings: Settings = Depends(get_settings),
) -> UploadSettings:
    """Provide upload settings."""
    return settings.upload


def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_batch_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AudioBatchRepository:
    return SqlAlchemyAudioBatchRepository(session)


def get_audio_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AudioRepository:
    return SqlAlchemyAudioRepository(session)


def get_job_repository(
    session: AsyncSession = Depends(get_db_session),
) -> JobRepository:
    return SqlAlchemyJobRepository(session)


def get_upload_service(
    upload_settings: UploadSettings = Depends(get_upload_settings),
    storage: StorageProvider = Depends(get_storage),
    users: UserRepository = Depends(get_user_repository),
    batches: AudioBatchRepository = Depends(get_batch_repository),
    assets: AudioRepository = Depends(get_audio_repository),
    jobs: JobRepository = Depends(get_job_repository),
) -> UploadService:
    """Construct UploadService via dependency injection."""
    return UploadService(
        settings=upload_settings,
        storage=storage,
        users=users,
        batches=batches,
        assets=assets,
        jobs=jobs,
    )
