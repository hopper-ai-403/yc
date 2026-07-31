"""Immutable domain value objects.

Business rules encoded here:
- Confidence must be between 0 and 1.
- Noise type must be empty or NONE when no noise exists.
- Noise severity must be NONE when no noise exists.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.shared.domain.enums import (
    AudioQuality,
    EmotionIntensity,
    EmotionTone,
    NoiseSeverity,
)
from app.shared.domain.exceptions import InvariantViolationException


class EmotionResult(BaseModel):
    """Emotion analyzer output."""

    model_config = ConfigDict(frozen=True)

    tone: EmotionTone
    intensity: EmotionIntensity


class NoiseResult(BaseModel):
    """Background noise analyzer output."""

    model_config = ConfigDict(frozen=True)

    present: bool
    type: str = ""
    severity: NoiseSeverity = NoiseSeverity.NONE

    @model_validator(mode="after")
    def validate_noise_invariants(self) -> "NoiseResult":
        if not self.present:
            if self.type.strip() and self.type.strip().upper() != "NONE":
                raise InvariantViolationException(
                    "Noise type must be empty or NONE when no noise exists",
                    details={"type": self.type, "present": self.present},
                )
            if self.severity is not NoiseSeverity.NONE:
                raise InvariantViolationException(
                    "Noise severity must be NONE when no noise exists",
                    details={
                        "severity": self.severity.value,
                        "present": self.present,
                    },
                )
        return self


class QualityResult(BaseModel):
    """Audio quality analyzer output."""

    model_config = ConfigDict(frozen=True)

    quality: AudioQuality


class OverlapResult(BaseModel):
    """Speaker overlap analyzer output."""

    model_config = ConfigDict(frozen=True)

    present: bool


class SilenceResult(BaseModel):
    """Long silence analyzer output."""

    model_config = ConfigDict(frozen=True)

    present: bool


class ConfidenceScore(BaseModel):
    """Aggregate prediction confidence in [0, 1]."""

    model_config = ConfigDict(frozen=True)

    value: float

    @field_validator("value")
    @classmethod
    def validate_range(cls, value: float) -> float:
        if value < 0.0 or value > 1.0:
            raise InvariantViolationException(
                "Confidence must be between 0 and 1",
                details={"value": value},
            )
        return value


class AudioMetadata(BaseModel):
    """Technical metadata extracted from an audio file."""

    model_config = ConfigDict(frozen=True)

    duration: float = Field(ge=0)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    bitrate: int | None = Field(default=None, ge=0)


class PredictionResult(BaseModel):
    """Aggregated immutable prediction payload for one audio asset."""

    model_config = ConfigDict(frozen=True)

    emotion: EmotionResult
    noise: NoiseResult
    quality: QualityResult
    overlap: OverlapResult
    silence: SilenceResult
    confidence: ConfidenceScore
