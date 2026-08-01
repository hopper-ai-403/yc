"""Factory for PreprocessingService outside FastAPI DI."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.preprocessing.ffmpeg import FFmpegClient
from app.audio.preprocessing.ffprobe import FFprobeClient
from app.audio.preprocessing.normalizer import AudioNormalizer
from app.audio.preprocessing.pipeline import PreprocessingPipeline
from app.audio.preprocessing.service import PreprocessingService
from app.audio.preprocessing.validator import AudioValidator
from app.audio.repository import SqlAlchemyAudioRepository
from app.config.settings import PreprocessingSettings, get_settings
from app.infrastructure.r2.client import CloudflareR2Storage
from app.shared.storage.provider import StorageProvider


def build_preprocessing_service(
    session: AsyncSession,
    *,
    storage: StorageProvider | None = None,
    settings: PreprocessingSettings | None = None,
) -> PreprocessingService:
    """Construct PreprocessingService with concrete collaborators."""
    preprocess_settings = settings or get_settings().preprocessing
    storage_provider = storage or CloudflareR2Storage(get_settings().r2)
    ffprobe = FFprobeClient(preprocess_settings)
    ffmpeg = FFmpegClient(preprocess_settings)
    validator = AudioValidator(preprocess_settings)
    normalizer = AudioNormalizer(preprocess_settings, ffmpeg, validator)
    pipeline = PreprocessingPipeline(
        settings=preprocess_settings,
        storage=storage_provider,
        ffprobe=ffprobe,
        ffmpeg=ffmpeg,
        validator=validator,
        normalizer=normalizer,
    )
    return PreprocessingService(
        assets=SqlAlchemyAudioRepository(session),
        pipeline=pipeline,
        settings=preprocess_settings,
    )
