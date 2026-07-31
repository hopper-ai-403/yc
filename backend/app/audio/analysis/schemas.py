"""Schemas for reusable audio analysis artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ANALYSIS_VERSION = "1.0.0"


class TimeSegment(BaseModel):
    """Inclusive-start exclusive-end time segment in seconds."""

    model_config = ConfigDict(frozen=True)

    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


class VADResult(BaseModel):
    """Voice activity detection outputs."""

    model_config = ConfigDict(frozen=True)

    speech_segments: list[TimeSegment] = Field(default_factory=list)
    silence_segments: list[TimeSegment] = Field(default_factory=list)
    speech_duration: float = Field(ge=0)
    speech_ratio: float = Field(ge=0, le=1)
    largest_silence: float = Field(ge=0)
    speech_start: float | None = None
    speech_end: float | None = None


class SignalFeatures(BaseModel):
    """Signal-level features shared by future AI engines."""

    model_config = ConfigDict(frozen=True)

    duration: float = Field(ge=0)
    rms_energy: float
    peak_amplitude: float
    zero_crossing_rate: float
    spectral_centroid: float
    spectral_bandwidth: float
    spectral_rolloff: float
    mfcc: list[float] = Field(min_length=13, max_length=13)
    pitch_f0: float | None = None
    tempo_estimate: float | None = None
    dynamic_range: float
    snr_estimate: float | None = None
    sample_rate: int = Field(gt=0)


class AnalysisArtifact(BaseModel):
    """Full analysis artifact persisted to R2 / returned by API."""

    model_config = ConfigDict(frozen=True)

    audio_id: str
    batch_id: str
    version: str = ANALYSIS_VERSION
    sample_rate: int
    vad: VADResult
    features: SignalFeatures

    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
