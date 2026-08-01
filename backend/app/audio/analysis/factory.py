"""Factory for AnalysisService outside FastAPI DI."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.analysis.features import FeatureExtractor
from app.audio.analysis.pipeline import AnalysisPipeline
from app.audio.analysis.service import AnalysisService
from app.audio.analysis.vad import (
    EnergyVAD,
    ResilientVAD,
    SileroVAD,
    VoiceActivityDetector,
)
from app.audio.repository import SqlAlchemyAudioRepository
from app.config.settings import AnalysisSettings, get_settings
from app.infrastructure.r2.client import CloudflareR2Storage
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)


def build_vad(settings: AnalysisSettings) -> VoiceActivityDetector:
    """Construct the configured VAD backend.

    Silero is preferred; on load/inference failure the resilient wrapper falls
    back to energy VAD so a single torch.hub outage cannot fail every audio.
    """
    if settings.vad_backend == "energy":
        return EnergyVAD()
    logger.info("vad_backend_selected", backend="silero", status="ok")
    return ResilientVAD(SileroVAD(settings), EnergyVAD())


def build_analysis_service(
    session: AsyncSession,
    *,
    storage: StorageProvider | None = None,
    settings: AnalysisSettings | None = None,
    vad: VoiceActivityDetector | None = None,
) -> AnalysisService:
    """Construct AnalysisService with concrete collaborators."""
    analysis_settings = settings or get_settings().analysis
    storage_provider = storage or CloudflareR2Storage(get_settings().r2)
    detector = vad or build_vad(analysis_settings)
    pipeline = AnalysisPipeline(
        settings=analysis_settings,
        storage=storage_provider,
        vad=detector,
        features=FeatureExtractor(),
    )
    return AnalysisService(
        assets=SqlAlchemyAudioRepository(session),
        pipeline=pipeline,
        storage=storage_provider,
    )
