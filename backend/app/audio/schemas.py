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
