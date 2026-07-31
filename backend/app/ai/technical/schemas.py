"""Technical intelligence schemas (assessment-aligned)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.shared.domain.enums import AudioQuality

TECHNICAL_VERSION = "1.0.0"


class QualityBreakdown(BaseModel):
    """Deterministic quality scoring components."""

    model_config = ConfigDict(frozen=True)

    snr_penalty: float = 0.0
    clipping_penalty: float = 0.0
    dynamic_range_penalty: float = 0.0
    silence_penalty: float = 0.0
    speech_presence_penalty: float = 0.0
    total_penalty: float = Field(ge=0)


class TechnicalResult(BaseModel):
    """Technical analysis output for one audio asset."""

    model_config = ConfigDict(frozen=True)

    audio_id: str
    batch_id: str
    version: str = TECHNICAL_VERSION
    audio_quality: AudioQuality
    speaker_overlap_present: bool
    long_silence_present: bool
    quality_score: float = Field(ge=0, le=100)
    quality_breakdown: QualityBreakdown
    overlap_score: float = Field(ge=0, le=1)
    overlap_details: dict[str, float] = Field(default_factory=dict)
    silence_details: dict[str, float] = Field(default_factory=dict)

    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class TechnicalRead(BaseModel):
    """API response payload."""

    audio_id: str
    audio_quality: AudioQuality
    speaker_overlap_present: bool
    long_silence_present: bool
    technical_version: str
    technical_completed: bool
