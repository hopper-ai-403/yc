"""Audio feature FastAPI dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.repository import AudioRepository, SqlAlchemyAudioRepository
from app.audio.service import AudioQueryService
from app.config.settings import R2Settings, Settings, get_settings
from app.dependencies import get_db_session, get_storage
from app.shared.storage.provider import StorageProvider


def get_audio_repository(
    session: AsyncSession = Depends(get_db_session),
) -> AudioRepository:
    return SqlAlchemyAudioRepository(session)


def get_r2_settings(settings: Settings = Depends(get_settings)) -> R2Settings:
    return settings.r2


def get_audio_query_service(
    assets: AudioRepository = Depends(get_audio_repository),
    storage: StorageProvider = Depends(get_storage),
    r2_settings: R2Settings = Depends(get_r2_settings),
) -> AudioQueryService:
    return AudioQueryService(
        assets=assets,
        storage=storage,
        r2_settings=r2_settings,
    )
