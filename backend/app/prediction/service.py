"""Prediction Engine application service.

Purpose: The ONLY orchestration layer that produces final assessment output.
Responsibilities: Idempotent prediction generation, regeneration on explicit
    retry, reads via PredictionRepository (Single Source of Truth).
Dependencies: AudioRepository, PredictionRepository, PredictionPipeline.
Extension points: ConfidenceEstimator implementations swapped via factory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.audio.preprocessing.exceptions import AudioAssetNotFoundException
from app.audio.repository import AudioRepository
from app.config.settings import PredictionSettings
from app.prediction.exceptions import PredictionNotFoundException
from app.prediction.models import Prediction
from app.prediction.pipeline import PredictionPipeline
from app.prediction.repository import PredictionRepository
from app.prediction.schemas import AssessmentPrediction, PredictionRead
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class PredictionService:
    """Coordinates prediction generation and persistence."""

    def __init__(
        self,
        *,
        assets: AudioRepository,
        predictions: PredictionRepository,
        pipeline: PredictionPipeline,
        settings: PredictionSettings,
    ) -> None:
        self._assets = assets
        self._predictions = predictions
        self._pipeline = pipeline
        self._settings = settings

    async def generate_prediction(
        self,
        audio_id: UUID,
        *,
        regenerate: bool = False,
        profile: dict[str, Any] | None = None,
    ) -> AssessmentPrediction:
        asset = await self._assets.find_by_id(audio_id)
        if asset is None:
            raise AudioAssetNotFoundException(audio_id)

        existing = await self._predictions.find_by_audio_asset(audio_id)
        if existing is not None and not regenerate:
            logger.info(
                "prediction_skipped_idempotent",
                audio_id=str(audio_id),
                prediction_version=existing.prediction_version,
            )
            return self._to_assessment(existing)

        prediction, breakdown, internal = await self._pipeline.run(
            asset,
            profile=profile,
        )
        internal_dict = internal.to_storage_dict() if internal is not None else None
        if internal_dict is not None and profile is not None:
            internal_dict["profile"] = profile
        await self._predictions.save_engine_result(
            audio_id,
            prediction_version=self._settings.prediction_version,
            prediction_json=prediction.to_public_dict(),
            internal_prediction_json=internal_dict,
            confidence_breakdown=breakdown.to_dict(),
            prediction_completed_at=datetime.now(timezone.utc),
            regenerate=regenerate,
        )
        logger.info(
            "PredictionPersisted",
            audio_id=str(audio_id),
            prediction_version=self._settings.prediction_version,
            confidence=prediction.confidence,
            regenerated=regenerate and existing is not None,
            status="ok",
        )
        return prediction

    async def get_prediction(self, audio_id: UUID) -> PredictionRead:
        prediction = await self._predictions.find_by_audio_asset(audio_id)
        if prediction is None:
            raise PredictionNotFoundException(
                f"Prediction not found for audio: {audio_id}",
                details={"audio_id": str(audio_id)},
            )
        return self._to_read(prediction)

    async def list_by_batch(self, batch_id: UUID) -> list[PredictionRead]:
        predictions = await self._predictions.find_by_batch(batch_id)
        return [self._to_read(prediction) for prediction in predictions]

    async def list_by_job(self, job_id: UUID) -> list[PredictionRead]:
        predictions = await self._predictions.find_by_job(job_id)
        return [self._to_read(prediction) for prediction in predictions]

    def _to_read(self, prediction: Prediction) -> PredictionRead:
        return PredictionRead(
            audio_id=str(prediction.audio_asset_id),
            prediction_version=prediction.prediction_version,
            prediction=self._public_payload(prediction),
        )

    def _to_assessment(self, prediction: Prediction) -> AssessmentPrediction:
        return AssessmentPrediction.model_validate(self._public_payload(prediction))

    @staticmethod
    def _public_payload(prediction: Prediction) -> dict[str, object]:
        if prediction.prediction_json:
            return dict(prediction.prediction_json)
        return {
            "emotional_tone": prediction.emotional_tone.value,
            "emotional_intensity": prediction.emotional_intensity.value,
            "background_noise_present": prediction.background_noise_present,
            "background_noise_type": prediction.background_noise_type,
            "background_noise_severity": prediction.background_noise_severity.value,
            "audio_quality": prediction.audio_quality.value,
            "speaker_overlap_present": prediction.speaker_overlap,
            "long_silence_present": prediction.long_silence,
            "confidence": prediction.confidence,
        }
