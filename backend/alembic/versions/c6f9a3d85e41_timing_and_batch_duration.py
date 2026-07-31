"""Add timing_json to audio_assets and batch_duration_ms to batch_metrics.

Revision ID: c6f9a3d85e41
Revises: b5e8f2a74c30
Create Date: 2026-08-01 00:05:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c6f9a3d85e41"
down_revision = "b5e8f2a74c30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audio_assets",
        sa.Column("timing_json", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "batch_metrics",
        sa.Column("batch_duration_ms", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("batch_metrics", "batch_duration_ms")
    op.drop_column("audio_assets", "timing_json")
