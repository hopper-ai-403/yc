"""Acoustic intelligence schemas (assessment-aligned)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.shared.domain.enums import NoiseSeverity, NoiseType

ACOUSTIC_VERSION = "1.0.0"


class AcousticResult(BaseModel):
    """Acoustic analysis output for one audio asset."""

    model_config = ConfigDict(frozen=True)

    audio_id: str
    batch_id: str
    version: str = ACOUSTIC_VERSION
    background_noise_present: bool
    background_noise_type: NoiseType
    background_noise_severity: NoiseSeverity
    noise_score: float = Field(ge=0, le=1)
    noise_details: dict[str, float] = Field(default_factory=dict)
    classification_details: dict[str, float] = Field(default_factory=dict)
    severity_details: dict[str, float] = Field(default_factory=dict)

    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AcousticRead(BaseModel):
    """API response payload."""

    audio_id: str
    background_noise_present: bool
    background_noise_type: NoiseType
    background_noise_severity: NoiseSeverity
    acoustic_version: str
    acoustic_completed: bool
