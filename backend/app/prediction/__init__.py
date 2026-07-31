"""Prediction feature module.

Purpose: Final assessment output — the only orchestration layer over the
    independent AI engines.
Responsibilities: Aggregation, validation, confidence, immutable persistence,
    public export.
Dependencies: ai.technical / ai.acoustic / ai.speech result schemas, audio,
    shared.domain, StorageProvider.
Extension points: ConfidenceEstimator implementations, export projections.
"""

from app.prediction.models import Prediction
from app.prediction.repository import (
    PredictionRepository,
    SqlAlchemyPredictionRepository,
)
from app.prediction.service import PredictionService

__all__ = [
    "Prediction",
    "PredictionRepository",
    "PredictionService",
    "SqlAlchemyPredictionRepository",
]
