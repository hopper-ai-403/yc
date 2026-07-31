"""Factory for SpeechService outside FastAPI DI."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.speech.analyzer import SpeechAnalyzer
from app.ai.speech.inference import get_or_load_model
from app.ai.speech.model import SpeechEmotionModel
from app.ai.speech.pipeline import SpeechPipeline
from app.ai.speech.service import SpeechService
from app.audio.repository import SqlAlchemyAudioRepository
from app.config.settings import SpeechSettings, get_settings
from app.infrastructure.r2.client import CloudflareR2Storage
from app.shared.storage.provider import StorageProvider


def build_speech_model(settings: SpeechSettings) -> SpeechEmotionModel:
    """Return the process-wide singleton SER model (loaded once per worker)."""
    return get_or_load_model(settings)


def build_speech_service(
    session: AsyncSession,
    *,
    storage: StorageProvider | None = None,
    settings: SpeechSettings | None = None,
    model: SpeechEmotionModel | None = None,
) -> SpeechService:
    """Construct SpeechService with concrete collaborators."""
    speech_settings = settings or get_settings().speech
    storage_provider = storage or CloudflareR2Storage(get_settings().r2)
    analyzer = SpeechAnalyzer(
        model=model or build_speech_model(speech_settings),
        settings=speech_settings,
    )
    pipeline = SpeechPipeline(
        storage=storage_provider,
        analyzer=analyzer,
        settings=speech_settings,
    )
    return SpeechService(
        assets=SqlAlchemyAudioRepository(session),
        pipeline=pipeline,
    )
