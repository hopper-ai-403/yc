"""Prediction feature module.

Purpose: Immutable prediction persistence.
Responsibilities: Prediction model and repository.
Dependencies: audio, shared.database, shared.domain.
Extension points: Aggregation service, export projections.
"""

from app.prediction.models import Prediction
from app.prediction.repository import (
    PredictionRepository,
    SqlAlchemyPredictionRepository,
)

__all__ = [
    "Prediction",
    "PredictionRepository",
    "SqlAlchemyPredictionRepository",
]
