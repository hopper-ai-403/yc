"""Create batch_metrics table.

Revision ID: b5e8f2a74c30
Revises: a4d7e1f63b29
Create Date: 2026-07-31 23:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b5e8f2a74c30"
down_revision = "a4d7e1f63b29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "batch_metrics",
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("total_audio", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "successful_predictions",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "failed_predictions", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("average_processing_time_ms", sa.Float(), nullable=True),
        sa.Column("min_processing_time_ms", sa.Float(), nullable=True),
        sa.Column("max_processing_time_ms", sa.Float(), nullable=True),
        sa.Column("average_confidence", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["audio_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", name="uq_batch_metrics_batch_id"),
    )
    op.create_index("ix_batch_metrics_batch_id", "batch_metrics", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_batch_metrics_batch_id", table_name="batch_metrics")
    op.drop_table("batch_metrics")
