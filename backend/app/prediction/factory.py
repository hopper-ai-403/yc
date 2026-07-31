"""Factory for Prediction Engine services outside FastAPI DI."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.repository import SqlAlchemyAudioRepository
from app.config.settings import PredictionSettings, get_settings
from app.infrastructure.r2.client import CloudflareR2Storage
from app.prediction.aggregator import PredictionAggregator
from app.prediction.builder import PredictionBuilder
from app.prediction.confidence import ConfidenceEstimator, WeightedConfidenceEstimator
from app.prediction.export import PredictionExportService
from app.prediction.pipeline import PredictionPipeline
from app.prediction.repository import (
    PredictionRepository,
    SqlAlchemyPredictionRepository,
)
from app.prediction.service import PredictionService
from app.prediction.validator import PredictionValidator
from app.shared.storage.provider import StorageProvider


def build_confidence_estimator(settings: PredictionSettings) -> ConfidenceEstimator:
    """Construct the configured confidence estimator implementation."""
    # Swappable: future calibrated estimator lands here.
    return WeightedConfidenceEstimator(settings)


def build_prediction_service(
    session: AsyncSession,
    *,
    storage: StorageProvider | None = None,
    settings: PredictionSettings | None = None,
    estimator: ConfidenceEstimator | None = None,
) -> PredictionService:
    """Construct PredictionService with concrete collaborators."""
    prediction_settings = settings or get_settings().prediction
    storage_provider = storage or CloudflareR2Storage(get_settings().r2)
    pipeline = PredictionPipeline(
        storage=storage_provider,
        aggregator=PredictionAggregator(),
        confidence=estimator or build_confidence_estimator(prediction_settings),
        builder=PredictionBuilder(),
        validator=PredictionValidator(
            confidence_rounding=prediction_settings.confidence_rounding,
        ),
        settings=prediction_settings,
    )
    return PredictionService(
        assets=SqlAlchemyAudioRepository(session),
        predictions=SqlAlchemyPredictionRepository(session),
        pipeline=pipeline,
        settings=prediction_settings,
    )


def build_prediction_export_service(
    session: AsyncSession,
    *,
    repository: PredictionRepository | None = None,
) -> PredictionExportService:
    """Construct PredictionExportService."""
    return PredictionExportService(
        predictions=repository or SqlAlchemyPredictionRepository(session),
    )
