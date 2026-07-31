"""Prediction repository contract and SQLAlchemy implementation.

Predictions become immutable after persistence (Rule 4 / domain invariant).
Single Source of Truth for all prediction reads and writes.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.prediction.models import Prediction
from app.shared.domain.enums import NoiseSeverity
from app.shared.domain.exceptions import (
    ImmutableEntityException,
    InvariantViolationException,
)
from app.shared.domain.value_objects import PredictionResult


class PredictionRepository(ABC):
    """Persistence contract for Prediction entities."""

    @abstractmethod
    async def save(self, prediction: Prediction) -> Prediction:
        """Persist a new prediction and mark it immutable."""

    @abstractmethod
    async def save_from_result(
        self,
        audio_asset_id: UUID,
        result: PredictionResult,
    ) -> Prediction:
        """Create and persist a prediction from a value object."""

    @abstractmethod
    async def find_by_id(self, prediction_id: UUID) -> Prediction | None:
        """Find a prediction by id."""

    @abstractmethod
    async def find_by_audio_asset(self, audio_asset_id: UUID) -> Prediction | None:
        """Find the prediction for an audio asset."""

    @abstractmethod
    async def find_by_batch(self, batch_id: UUID) -> list[Prediction]:
        """List predictions for all assets in a batch."""

    @abstractmethod
    async def find_by_job(self, job_id: UUID) -> list[Prediction]:
        """List predictions for all assets processed by a job."""

    @abstractmethod
    async def save_engine_result(
        self,
        audio_asset_id: UUID,
        *,
        prediction_version: str,
        prediction_json: dict[str, Any],
        internal_prediction_json: dict[str, Any] | None,
        confidence_breakdown: dict[str, Any],
        prediction_completed_at: datetime,
        regenerate: bool = False,
    ) -> Prediction:
        """Persist Prediction Engine output.

        Existing predictions are never overwritten unless ``regenerate`` is
        explicitly requested.
        """


class SqlAlchemyPredictionRepository(PredictionRepository):
    """SQLAlchemy-backed PredictionRepository with immutability enforcement."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, prediction: Prediction) -> Prediction:
        prediction.assert_mutable()
        self._validate_noise_invariants(prediction)
        prediction.is_persisted = True
        self._session.add(prediction)
        await self._session.flush()
        await self._session.refresh(prediction)
        return prediction

    async def save_from_result(
        self,
        audio_asset_id: UUID,
        result: PredictionResult,
    ) -> Prediction:
        prediction = Prediction.from_result(audio_asset_id, result)
        return await self.save(prediction)

    async def find_by_id(self, prediction_id: UUID) -> Prediction | None:
        return await self._session.get(Prediction, prediction_id)

    async def find_by_audio_asset(self, audio_asset_id: UUID) -> Prediction | None:
        statement = select(Prediction).where(
            Prediction.audio_asset_id == audio_asset_id
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def find_by_batch(self, batch_id: UUID) -> list[Prediction]:
        from app.audio.models import AudioAsset

        statement = (
            select(Prediction)
            .join(AudioAsset, Prediction.audio_asset_id == AudioAsset.id)
            .where(AudioAsset.batch_id == batch_id)
            .order_by(AudioAsset.filename)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def find_by_job(self, job_id: UUID) -> list[Prediction]:
        from app.audio.models import AudioAsset
        from app.jobs.models import Job

        statement = (
            select(Prediction)
            .join(AudioAsset, Prediction.audio_asset_id == AudioAsset.id)
            .join(Job, Job.batch_id == AudioAsset.batch_id)
            .where(Job.id == job_id)
            .order_by(AudioAsset.filename)
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def save_engine_result(
        self,
        audio_asset_id: UUID,
        *,
        prediction_version: str,
        prediction_json: dict[str, Any],
        internal_prediction_json: dict[str, Any] | None,
        confidence_breakdown: dict[str, Any],
        prediction_completed_at: datetime,
        regenerate: bool = False,
    ) -> Prediction:
        from app.prediction.exceptions import PredictionAlreadyExistsException

        existing = await self.find_by_audio_asset(audio_asset_id)
        if existing is not None:
            if not regenerate:
                raise PredictionAlreadyExistsException(
                    audio_asset_id,
                    prediction_id=existing.id,
                )
            await self._session.delete(existing)
            await self._session.flush()

        payload = dict(prediction_json)
        prediction = Prediction(
            audio_asset_id=audio_asset_id,
            emotional_tone=payload["emotional_tone"],
            emotional_intensity=payload["emotional_intensity"],
            background_noise_present=payload["background_noise_present"],
            background_noise_type=payload["background_noise_type"],
            background_noise_severity=payload["background_noise_severity"],
            audio_quality=payload["audio_quality"],
            speaker_overlap=payload["speaker_overlap_present"],
            long_silence=payload["long_silence_present"],
            confidence=payload["confidence"],
            is_persisted=True,
            prediction_version=prediction_version,
            prediction_completed_at=prediction_completed_at,
            prediction_json=payload,
            internal_prediction_json=(
                dict(internal_prediction_json)
                if internal_prediction_json is not None
                else None
            ),
            confidence_breakdown=dict(confidence_breakdown),
        )
        self._validate_noise_invariants(prediction)
        self._session.add(prediction)
        await self._session.flush()
        await self._session.refresh(prediction)
        return prediction

    async def update(self, prediction: Prediction) -> Prediction:
        """Rejected: predictions are immutable after persistence."""
        raise ImmutableEntityException(
            "Prediction is immutable after persistence",
            details={"prediction_id": str(prediction.id)},
        )

    async def delete(self, prediction_id: UUID) -> None:
        """Rejected: predictions are immutable after persistence."""
        raise ImmutableEntityException(
            "Prediction is immutable after persistence",
            details={"prediction_id": str(prediction_id)},
        )

    @staticmethod
    def _validate_noise_invariants(prediction: Prediction) -> None:
        if not prediction.background_noise_present:
            noise_type = prediction.background_noise_type.strip()
            if noise_type and noise_type.upper() != "NONE":
                raise InvariantViolationException(
                    "Noise type must be empty or NONE when no noise exists",
                    details={"type": prediction.background_noise_type},
                )
            if prediction.background_noise_severity is not NoiseSeverity.NONE:
                raise InvariantViolationException(
                    "Noise severity must be NONE when no noise exists",
                    details={
                        "severity": prediction.background_noise_severity.value,
                    },
                )
