"""Job processing domain models.

Purpose: Persist asynchronous batch processing jobs.
Responsibilities: Job entity mapping; one job per batch invariant.
Dependencies: audio.models, shared.database, shared.domain.enums.
Extension points: Stage-level progress, worker assignment.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.shared.database.enums import pg_enum
from app.shared.domain.enums import JobStatus

if TYPE_CHECKING:
    from app.audio.models import AudioBatch


class Job(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Asynchronous processing job owned by exactly one batch."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("batch_id", name="uq_jobs_batch_id"),
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_jobs_progress_range",
        ),
        CheckConstraint("retry_count >= 0", name="ck_jobs_retry_count_nonnegative"),
    )

    batch_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("audio_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, name="job_status"),
        nullable=False,
        default=JobStatus.PENDING,
        index=True,
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    batch: Mapped[AudioBatch] = relationship(back_populates="job", lazy="joined")
