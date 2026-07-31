"""Factory for TechnicalService outside FastAPI DI."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.technical.analyzer import TechnicalAnalyzer
from app.ai.technical.overlap import OverlapDetector, SignalBasedOverlapDetector
from app.ai.technical.pipeline import TechnicalPipeline
from app.ai.technical.quality import AudioQualityAnalyzer
from app.ai.technical.service import TechnicalService
from app.ai.technical.silence import LongSilenceDetector
from app.audio.repository import SqlAlchemyAudioRepository
from app.config.settings import TechnicalSettings, get_settings
from app.infrastructure.r2.client import CloudflareR2Storage
from app.shared.storage.provider import StorageProvider


def build_overlap_detector(settings: TechnicalSettings) -> OverlapDetector:
    """Construct the configured overlap detector implementation."""
    # Swappable: future "pyannote" / "neural" implementations land here.
    return SignalBasedOverlapDetector(settings)


def build_technical_service(
    session: AsyncSession,
    *,
    storage: StorageProvider | None = None,
    settings: TechnicalSettings | None = None,
    overlap_detector: OverlapDetector | None = None,
) -> TechnicalService:
    """Construct TechnicalService with concrete collaborators."""
    technical_settings = settings or get_settings().technical
    storage_provider = storage or CloudflareR2Storage(get_settings().r2)
    analyzer = TechnicalAnalyzer(
        silence=LongSilenceDetector(technical_settings),
        quality=AudioQualityAnalyzer(technical_settings),
        overlap=overlap_detector or build_overlap_detector(technical_settings),
    )
    pipeline = TechnicalPipeline(
        storage=storage_provider,
        analyzer=analyzer,
    )
    return TechnicalService(
        assets=SqlAlchemyAudioRepository(session),
        pipeline=pipeline,
    )
