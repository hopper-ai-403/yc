"""Factory for TechnicalService outside FastAPI DI."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.technical.analyzer import TechnicalAnalyzer
from app.ai.technical.overlap import (
    OverlapDetector,
    PyannoteOverlapDetector,
    SignalBasedOverlapDetector,
)
from app.ai.technical.overlap_model import pyannote_dependency_available
from app.ai.technical.pipeline import TechnicalPipeline
from app.ai.technical.quality import AudioQualityAnalyzer
from app.ai.technical.service import TechnicalService
from app.ai.technical.silence import LongSilenceDetector
from app.audio.repository import SqlAlchemyAudioRepository
from app.config.settings import TechnicalSettings, get_settings
from app.infrastructure.r2.client import CloudflareR2Storage
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)


def build_overlap_detector(settings: TechnicalSettings) -> OverlapDetector:
    """Construct the configured overlap detector implementation.

    ``TECHNICAL_OVERLAP_BACKEND=pyannote`` (default) selects pyannote when the
    dependency is importable; otherwise falls back to the heuristic. Explicit
    ``heuristic`` always uses ``SignalBasedOverlapDetector``.
    """
    backend = (settings.overlap_backend or "pyannote").strip().lower()
    if backend == "heuristic":
        logger.info(
            "overlap_backend_selected",
            backend="heuristic",
            selected_implementation="SignalBasedOverlapDetector",
            status="ok",
        )
        return SignalBasedOverlapDetector(settings)

    if backend != "pyannote":
        logger.warning(
            "overlap_backend_unknown",
            backend=backend,
            selected_implementation="SignalBasedOverlapDetector",
            status="fallback",
        )
        return SignalBasedOverlapDetector(settings)

    if not pyannote_dependency_available():
        logger.warning(
            "overlap_backend_unavailable",
            backend="pyannote",
            reason="dependency_missing",
            selected_implementation="SignalBasedOverlapDetector",
            status="fallback",
        )
        return SignalBasedOverlapDetector(settings)

    logger.info(
        "overlap_backend_selected",
        backend="pyannote",
        model_version=settings.overlap_model_name,
        selected_implementation="PyannoteOverlapDetector",
        status="ok",
    )
    return PyannoteOverlapDetector(settings)


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
