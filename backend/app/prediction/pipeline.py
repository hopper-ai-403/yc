"""Prediction pipeline: aggregate → confidence → build → validate → upload."""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

from app.audio.models import AudioAsset
from app.config.settings import PredictionSettings
from app.prediction.aggregator import PredictionAggregator
from app.prediction.builder import PredictionBuilder
from app.prediction.confidence import ConfidenceEstimator
from app.prediction.schemas import (
    AssessmentPrediction,
    ConfidenceBreakdown,
    InternalPrediction,
)
from app.prediction.validator import PredictionValidator
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)


def prediction_storage_key(batch_id: UUID, audio_id: UUID) -> str:
    return f"uploads/{batch_id}/predictions/{audio_id}.json"


class PredictionPipeline:
    """Orchestrate the Prediction Engine stages for one asset."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        aggregator: PredictionAggregator,
        confidence: ConfidenceEstimator,
        builder: PredictionBuilder,
        validator: PredictionValidator,
        settings: PredictionSettings,
    ) -> None:
        self._storage = storage
        self._aggregator = aggregator
        self._confidence = confidence
        self._builder = builder
        self._validator = validator
        self._settings = settings

    async def run(
        self,
        asset: AudioAsset,
        *,
        profile: dict[str, Any] | None = None,
    ) -> tuple[AssessmentPrediction, ConfidenceBreakdown, InternalPrediction | None]:
        started = time.perf_counter()

        analysis = self._aggregator.aggregate(asset)
        breakdown = self._confidence.estimate(analysis)
        prediction = self._builder.build(analysis, breakdown)
        prediction = self._validator.validate(prediction)

        internal: InternalPrediction | None = None
        if self._settings.internal_prediction_enabled:
            internal = InternalPrediction(
                version=f"v{self._settings.prediction_version}",
                technical=analysis.technical.to_storage_dict(),
                acoustic=analysis.acoustic.to_storage_dict(),
                speech=analysis.speech.to_storage_dict(),
                confidence=breakdown,
                prediction=prediction,
            )
            payload = internal.to_storage_dict()
            if profile is not None:
                payload["profile"] = profile
            key = prediction_storage_key(asset.batch_id, asset.id)
            await self._storage.upload(
                key,
                json.dumps(payload).encode("utf-8"),
                content_type="application/json",
                metadata={
                    "audio_id": str(asset.id),
                    "batch_id": str(asset.batch_id),
                    "stage": "prediction",
                    "version": self._settings.prediction_version,
                },
            )
            logger.info(
                "prediction_uploaded",
                audio_id=str(asset.id),
                storage_key=key,
                duration_ms=int((time.perf_counter() - started) * 1000),
                status="ok",
            )
        return prediction, breakdown, internal
