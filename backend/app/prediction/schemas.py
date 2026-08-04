"""Prediction engine schemas.

Public schema matches the assessment contract exactly; internal schemas retain
full analysis provenance.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ai.acoustic.schemas import AcousticResult
from app.ai.speech.schemas import SpeechResult
from app.ai.technical.schemas import TechnicalResult
from app.shared.domain.enums import (
    AudioQuality,
    EmotionIntensity,
    EmotionTone,
    NoiseSeverity,
    NoiseType,
)

ASSESSMENT_FIELDS: tuple[str, ...] = (
    "emotional_tone",
    "emotional_intensity",
    "background_noise_present",
    "background_noise_type",
    "background_noise_severity",
    "audio_quality",
    "speaker_overlap_present",
    "long_silence_present",
    "confidence",
)


class AssessmentPrediction(BaseModel):
    """Public prediction — exactly the assessment schema, nothing else."""

    model_config = ConfigDict(frozen=True)

    emotional_tone: EmotionTone
    emotional_intensity: EmotionIntensity
    background_noise_present: bool
    background_noise_type: NoiseType
    background_noise_severity: NoiseSeverity
    audio_quality: AudioQuality
    speaker_overlap_present: bool
    long_silence_present: bool
    confidence: float = Field(ge=0.0, le=1.0)

    def to_public_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AnalysisResult(BaseModel):
    """Intermediate object: outputs of the three independent AI engines."""

    model_config = ConfigDict(frozen=True)

    technical: TechnicalResult
    acoustic: AcousticResult
    speech: SpeechResult


class ConfidenceBreakdown(BaseModel):
    """Per-engine confidence components."""

    model_config = ConfigDict(frozen=True)

    overall: float = Field(ge=0.0, le=1.0)
    speech: float = Field(ge=0.0, le=1.0)
    technical: float = Field(ge=0.0, le=1.0)
    acoustic: float = Field(ge=0.0, le=1.0)

    def to_dict(self) -> dict[str, float]:
        return self.model_dump(mode="json")


class InternalPrediction(BaseModel):
    """Full provenance payload persisted to R2 / internal DB column."""

    model_config = ConfigDict(frozen=True)

    version: str
    technical: dict[str, Any]
    acoustic: dict[str, Any]
    speech: dict[str, Any]
    confidence: ConfidenceBreakdown
    prediction: AssessmentPrediction

    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PredictionRead(BaseModel):
    """API payload: public prediction plus identifiers."""

    audio_id: str
    prediction_version: str | None = None
    filename: str | None = None
    prediction: dict[str, Any]


class PredictionListRead(BaseModel):
    """API payload for batch/job prediction listings."""

    count: int
    predictions: list[PredictionRead]
