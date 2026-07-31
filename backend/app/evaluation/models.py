"""Evaluation domain models.

Purpose: Persist per-batch evaluation metrics.
Responsibilities: BatchMetrics entity mapping; one metrics row per batch.
Dependencies: audio.models, shared.database.
Extension points: Additional aggregate columns.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BatchMetrics(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Aggregated evaluation metrics for exactly one batch."""

    __tablename__ = "batch_metrics"
    __table_args__ = (UniqueConstraint("batch_id", name="uq_batch_metrics_batch_id"),)

    batch_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("audio_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    total_audio: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_predictions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failed_predictions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    average_processing_time_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    min_processing_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_processing_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    batch_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
