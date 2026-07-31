"""Job API and service schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.jobs.models import Job
from app.shared.domain.enums import JobStatus


class JobRead(BaseModel):
    """Serialized job entity for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    status: JobStatus
    progress: int
    retry_count: int
    total_files: int
    processed_files: int
    failed_files: int
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, job: Job) -> JobRead:
        return cls.model_validate(job)


class JobProgressData(BaseModel):
    """Live progress snapshot for a job."""

    job_id: UUID
    status: JobStatus
    total_files: int
    processed_files: int
    failed_files: int
    progress_percentage: int = Field(ge=0, le=100)
    elapsed_time_ms: int | None = None
    retry_count: int = 0
    error_message: str | None = None

    @classmethod
    def from_entity(cls, job: Job) -> JobProgressData:
        elapsed: int | None = None
        if job.started_at is not None:
            end = job.completed_at or datetime.now(timezone.utc)
            started = job.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            elapsed = int((end - started).total_seconds() * 1000)
        return cls(
            job_id=job.id,
            status=job.status,
            total_files=job.total_files,
            processed_files=job.processed_files,
            failed_files=job.failed_files,
            progress_percentage=job.progress,
            elapsed_time_ms=elapsed,
            retry_count=job.retry_count,
            error_message=job.error_message,
        )


class JobListData(BaseModel):
    """Paginated job list payload."""

    items: list[JobRead]
    count: int


class StartJobData(BaseModel):
    """Response after enqueueing a job."""

    job: JobRead
    queued: bool = True


class JobActionData(BaseModel):
    """Generic job mutation response."""

    job: JobRead
    detail: dict[str, Any] = Field(default_factory=dict)
