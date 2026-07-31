"""Speech intelligence schemas (assessment-aligned)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.shared.domain.enums import EmotionIntensity, EmotionTone

SPEECH_VERSION = "1.0.0"


class SpeechResult(BaseModel):
    """Speech emotion output for one audio asset (normalized values only)."""

    model_config = ConfigDict(frozen=True)

    audio_id: str
    batch_id: str
    version: str = SPEECH_VERSION
    emotional_tone: EmotionTone
    emotional_intensity: EmotionIntensity
    top_probability: float = Field(ge=0, le=1)
    tone_probabilities: dict[str, float] = Field(default_factory=dict)
    model_name: str
    raw_label: str

    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SpeechRead(BaseModel):
    """API response payload."""

    audio_id: str
    emotional_tone: EmotionTone
    emotional_intensity: EmotionIntensity
    speech_version: str
    speech_completed: bool
