"""System module schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SystemMetricsRead(BaseModel):
    """Aggregate operational metrics for /system/metrics."""

    database: bool
    redis: bool
    r2: bool
    celery: bool
    model_loaded: bool
    worker_count: int = Field(ge=0)
    system_version: str
    checked_at: datetime


class WorkerRead(BaseModel):
    """One worker heartbeat record."""

    worker_id: str
    status: str
    last_heartbeat: datetime | None = None
    stale: bool


class WorkersRead(BaseModel):
    """Worker registry response."""

    worker_count: int = Field(ge=0)
    stale_count: int = Field(ge=0)
    workers: list[WorkerRead]


class BenchmarkRead(BaseModel):
    """Benchmark report for one evaluation batch."""

    batch_id: UUID
    total_files: int = Field(ge=0)
    successful_files: int = Field(ge=0)
    failed_files: int = Field(ge=0)
    average_latency_ms: float | None = None
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None
    batch_duration_ms: float | None = None
    throughput_files_per_minute: float | None = None
    average_confidence: float | None = None
    failure_rate: float = Field(ge=0.0, le=1.0)
