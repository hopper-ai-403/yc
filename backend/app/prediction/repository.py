"""Prediction repository contract and SQLAlchemy implementation.

Predictions become immutable after persistence (Rule 4 / domain invariant).
"""

from abc import ABC, abstractmethod
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
            if prediction.background_noise_type.strip():
                raise InvariantViolationException(
                    "Noise type must be empty when no noise exists",
                    details={"type": prediction.background_noise_type},
                )
            if prediction.background_noise_severity is not NoiseSeverity.NONE:
                raise InvariantViolationException(
                    "Noise severity must be NONE when no noise exists",
                    details={
                        "severity": prediction.background_noise_severity.value,
                    },
                )
