"""Audio asset API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.audio.models import AudioAsset
from app.shared.domain.enums import AudioStatus


class AudioAssetRead(BaseModel):
    """Serialized audio asset."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    filename: str
    format: str
    extension: str
    mime_type: str
    size_bytes: int
    duration: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    storage_key: str
    normalized_storage_key: str | None = None
    processing_status: AudioStatus
    is_preprocessed: bool
    preprocessed_at: datetime | None = None
    analysis_completed: bool = False
    analysis_storage_key: str | None = None
    analysis_version: str | None = None
    analysis_completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, asset: AudioAsset) -> AudioAssetRead:
        return cls.model_validate(asset)


class AudioMetadataRead(BaseModel):
    """Preprocessing metadata payload."""

    audio_id: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_preprocessed: bool


class AudioDownloadData(BaseModel):
    """Signed download URL for normalized (preferred) or original audio."""

    audio_id: UUID
    url: str
    storage_key: str
    content_variant: str
    expires_in: int


class AudioAnalysisRead(BaseModel):
    """Full analysis artifact response."""

    audio_id: UUID
    analysis_completed: bool
    analysis_version: str | None = None
    analysis_storage_key: str | None = None
    analysis: dict[str, Any] = Field(default_factory=dict)


class AudioTechnicalRead(BaseModel):
    """Technical intelligence response payload."""

    audio_id: UUID
    audio_quality: str
    speaker_overlap_present: bool
    long_silence_present: bool
    technical_version: str | None = None
    technical_completed: bool


class AudioAcousticRead(BaseModel):
    """Acoustic intelligence response payload."""

    audio_id: UUID
    background_noise_present: bool
    background_noise_type: str
    background_noise_severity: str
    acoustic_version: str | None = None
    acoustic_completed: bool


class AudioSpeechRead(BaseModel):
    """Speech intelligence response payload."""

    audio_id: UUID
    emotional_tone: str
    emotional_intensity: str
    speech_version: str | None = None
    speech_completed: bool


class AudioSegmentsRead(BaseModel):
    """Speech / silence segmentation subset."""

    audio_id: UUID
    speech_segments: list[dict[str, float]] = Field(default_factory=list)
    silence_segments: list[dict[str, float]] = Field(default_factory=list)
    speech_duration: float = 0.0
    speech_ratio: float = 0.0
    largest_silence: float = 0.0
    speech_start: float | None = None
    speech_end: float | None = None
