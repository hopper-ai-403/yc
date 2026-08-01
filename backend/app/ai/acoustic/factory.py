"""Factory for AcousticService outside FastAPI DI."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.acoustic.analyzer import AcousticAnalyzer
from app.ai.acoustic.classifier import HeuristicNoiseClassifier, NoiseClassifier
from app.ai.acoustic.detector import NoiseDetector, SignalBasedNoiseDetector
from app.ai.acoustic.event_classifier import HuggingFaceAudioEventClassifier
from app.ai.acoustic.pipeline import AcousticPipeline
from app.ai.acoustic.service import AcousticService
from app.ai.acoustic.severity import (
    DeterministicSeverityEstimator,
    NoiseSeverityEstimator,
)
from app.audio.repository import SqlAlchemyAudioRepository
from app.config.settings import AcousticSettings, get_settings
from app.infrastructure.r2.client import CloudflareR2Storage
from app.shared.storage.provider import StorageProvider


def build_noise_detector(settings: AcousticSettings) -> NoiseDetector:
    """Construct the configured noise detector implementation."""
    # Swappable: future neural detector lands here.
    return SignalBasedNoiseDetector(settings)


def build_noise_classifier(settings: AcousticSettings) -> NoiseClassifier:
    """Construct the configured noise classifier implementation."""
    fallback = HeuristicNoiseClassifier(settings)
    backend = settings.classifier_backend.strip().lower()
    if backend in {"heuristic", "signal"}:
        return fallback
    # Default: Hugging Face audio-event classification with heuristic fallback.
    return HuggingFaceAudioEventClassifier(settings, fallback=fallback)


def build_severity_estimator(settings: AcousticSettings) -> NoiseSeverityEstimator:
    """Construct the configured severity estimator implementation."""
    return DeterministicSeverityEstimator(settings)


def build_acoustic_service(
    session: AsyncSession,
    *,
    storage: StorageProvider | None = None,
    settings: AcousticSettings | None = None,
    detector: NoiseDetector | None = None,
    classifier: NoiseClassifier | None = None,
    severity: NoiseSeverityEstimator | None = None,
) -> AcousticService:
    """Construct AcousticService with concrete collaborators."""
    acoustic_settings = settings or get_settings().acoustic
    storage_provider = storage or CloudflareR2Storage(get_settings().r2)
    analyzer = AcousticAnalyzer(
        detector=detector or build_noise_detector(acoustic_settings),
        classifier=classifier or build_noise_classifier(acoustic_settings),
        severity=severity or build_severity_estimator(acoustic_settings),
    )
    pipeline = AcousticPipeline(
        storage=storage_provider,
        analyzer=analyzer,
    )
    return AcousticService(
        assets=SqlAlchemyAudioRepository(session),
        pipeline=pipeline,
    )
