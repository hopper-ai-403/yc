"""Audio preprocessing metadata schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProbeStream(BaseModel):
    """Relevant ffprobe stream fields."""

    model_config = ConfigDict(extra="ignore")

    codec_type: str | None = None
    codec_name: str | None = None
    sample_rate: str | int | None = None
    channels: int | None = None
    bit_rate: str | int | None = None
    duration: str | float | None = None


class ProbeFormat(BaseModel):
    """Relevant ffprobe format fields."""

    model_config = ConfigDict(extra="ignore")

    format_name: str | None = None
    duration: str | float | None = None
    size: str | int | None = None
    bit_rate: str | int | None = None


class ProbeResult(BaseModel):
    """Parsed ffprobe JSON payload."""

    model_config = ConfigDict(extra="ignore")

    streams: list[ProbeStream] = Field(default_factory=list)
    format: ProbeFormat | None = None


class AudioTechnicalMetadata(BaseModel):
    """Canonical preprocessing metadata persisted to DB and R2."""

    duration: float = Field(ge=0)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    bitrate: int | None = Field(default=None, ge=0)
    codec: str
    container: str
    file_size: int = Field(ge=0)
    peak_db: float | None = None
    rms_db: float | None = None
    normalized_sample_rate: int = Field(gt=0)
    normalized_channels: int = Field(gt=0)
    normalized_codec: str
    normalized_file_size: int | None = Field(default=None, ge=0)
    normalized_duration: float | None = Field(default=None, ge=0)

    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
