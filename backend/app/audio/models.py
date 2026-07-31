"""Audio management domain models.

Purpose: Persist audio batches and assets.
Responsibilities: Batch/asset entity mapping and ownership relationships.
Dependencies: auth.models, shared.database, shared.domain.enums.
Extension points: Manifest rows, format-specific metadata columns.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.shared.database.enums import pg_enum
from app.shared.domain.enums import AudioStatus, BatchStatus

if TYPE_CHECKING:
    from app.auth.models import User
    from app.jobs.models import Job
    from app.prediction.models import Prediction


class AudioBatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Uploaded ZIP batch aggregate root."""

    __tablename__ = "audio_batches"

    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[BatchStatus] = mapped_column(
        pg_enum(BatchStatus, name="batch_status"),
        nullable=False,
        default=BatchStatus.UPLOADED,
        index=True,
    )

    uploader: Mapped[User] = relationship(back_populates="batches", lazy="joined")
    assets: Mapped[list[AudioAsset]] = relationship(
        back_populates="batch",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    job: Mapped[Job | None] = relationship(
        back_populates="batch",
        lazy="joined",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AudioAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single audio recording belonging to exactly one batch."""

    __tablename__ = "audio_assets"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_audio_assets_storage_key"),
    )

    batch_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("audio_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    processing_status: Mapped[AudioStatus] = mapped_column(
        pg_enum(AudioStatus, name="audio_status"),
        nullable=False,
        default=AudioStatus.UPLOADED,
        index=True,
    )

    batch: Mapped[AudioBatch] = relationship(back_populates="assets", lazy="joined")
    prediction: Mapped[Prediction | None] = relationship(
        back_populates="audio_asset",
        lazy="joined",
        uselist=False,
        cascade="all, delete-orphan",
    )
