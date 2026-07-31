"""Prediction domain models.

Purpose: Persist immutable structured AI predictions.
Responsibilities: Prediction entity mapping; one prediction per audio asset.
Dependencies: audio.models, shared.database, shared.domain.
Extension points: Additional analyzer output columns.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.shared.database.enums import pg_enum
from app.shared.domain.enums import (
    AudioQuality,
    EmotionIntensity,
    EmotionTone,
    NoiseSeverity,
)
from app.shared.domain.exceptions import (
    ImmutableEntityException,
    InvariantViolationException,
)
from app.shared.domain.value_objects import PredictionResult

if TYPE_CHECKING:
    from app.audio.models import AudioAsset


class Prediction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Final structured analysis for exactly one audio asset.

    Immutable after persistence: updates and deletes are rejected by the
    repository and by ``assert_mutable``.
    """

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("audio_asset_id", name="uq_predictions_audio_asset_id"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_predictions_confidence_range",
        ),
    )

    audio_asset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("audio_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    emotional_tone: Mapped[EmotionTone] = mapped_column(
        pg_enum(EmotionTone, name="emotion_tone"),
        nullable=False,
    )
    emotional_intensity: Mapped[EmotionIntensity] = mapped_column(
        pg_enum(EmotionIntensity, name="emotion_intensity"),
        nullable=False,
    )
    background_noise_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    background_noise_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="",
    )
    background_noise_severity: Mapped[NoiseSeverity] = mapped_column(
        pg_enum(NoiseSeverity, name="noise_severity"),
        nullable=False,
        default=NoiseSeverity.NONE,
    )
    audio_quality: Mapped[AudioQuality] = mapped_column(
        pg_enum(AudioQuality, name="audio_quality"),
        nullable=False,
    )
    speaker_overlap: Mapped[bool] = mapped_column(Boolean, nullable=False)
    long_silence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    prediction_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prediction_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    prediction_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    internal_prediction_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_persisted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    audio_asset: Mapped[AudioAsset] = relationship(
        back_populates="prediction",
        lazy="joined",
    )

    def assert_mutable(self) -> None:
        """Raise if this prediction has already been persisted."""
        if self.is_persisted:
            raise ImmutableEntityException(
                "Prediction is immutable after persistence",
                details={"prediction_id": str(self.id)},
            )

    def apply_result(self, result: PredictionResult) -> None:
        """Populate columns from a validated PredictionResult value object."""
        self.assert_mutable()
        if not result.noise.present:
            noise_type = result.noise.type.strip()
            if noise_type and noise_type.upper() != "NONE":
                raise InvariantViolationException(
                    "Noise type must be empty or NONE when no noise exists"
                )
        if not result.noise.present and result.noise.severity is not NoiseSeverity.NONE:
            raise InvariantViolationException(
                "Noise severity must be NONE when no noise exists"
            )

        self.emotional_tone = result.emotion.tone
        self.emotional_intensity = result.emotion.intensity
        self.background_noise_present = result.noise.present
        self.background_noise_type = result.noise.type
        self.background_noise_severity = result.noise.severity
        self.audio_quality = result.quality.quality
        self.speaker_overlap = result.overlap.present
        self.long_silence = result.silence.present
        self.confidence = result.confidence.value

    @classmethod
    def from_result(cls, audio_asset_id: UUID, result: PredictionResult) -> Prediction:
        """Factory creating a new Prediction from a PredictionResult."""
        prediction = cls(audio_asset_id=audio_asset_id, is_persisted=False)
        prediction.apply_result(result)
        return prediction
