"""Evaluation schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BatchRunRead(BaseModel):
    """Response for POST /batches/{id}/run."""

    batch_id: UUID
    job_id: UUID
    status: str
    queued: bool
    already_running: bool


class BatchStatusRead(BaseModel):
    """Response for GET /batches/{id}/status."""

    batch_id: UUID
    job_id: UUID | None = None
    status: str
    progress: int = Field(ge=0, le=100)
    total_files: int = Field(ge=0)
    processed_files: int = Field(ge=0)
    failed_files: int = Field(ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    estimated_remaining_seconds: float | None = None


class BatchMetricsRead(BaseModel):
    """Response for GET /batches/{id}/metrics."""

    batch_id: UUID
    total_audio: int
    successful_predictions: int
    failed_predictions: int
    success_rate: float
    average_processing_time_ms: float | None = None
    min_processing_time_ms: float | None = None
    max_processing_time_ms: float | None = None
    average_confidence: float | None = None
    batch_duration_ms: float | None = None
    computed_at: datetime


class BatchExportItem(BaseModel):
    """One export artifact with a signed URL."""

    name: str
    storage_key: str
    url: str
    expires_in: int


class BatchExportsRead(BaseModel):
    """Response for GET /batches/{id}/exports."""

    batch_id: UUID
    exports: list[BatchExportItem]


class BatchExportJsonRead(BaseModel):
    """Response for GET /batches/{id}/export/json."""

    batch_id: UUID
    count: int
    results: list[dict]


class EvaluationMetricsData(BaseModel):
    """Internal computed metrics payload."""

    model_config = ConfigDict(frozen=True)

    total_audio: int
    successful_predictions: int
    failed_predictions: int
    success_rate: float
    average_processing_time_ms: float | None
    min_processing_time_ms: float | None
    max_processing_time_ms: float | None
    average_confidence: float | None
