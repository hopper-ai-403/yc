"""Add acoustic intelligence fields to audio_assets.

Revision ID: e2b5c9d41f07
Revises: d1f3a7b29c05
Create Date: 2026-07-31 23:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e2b5c9d41f07"
down_revision = "d1f3a7b29c05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audio_assets",
        sa.Column(
            "acoustic_completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "audio_assets",
        sa.Column("acoustic_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column("acoustic_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column(
            "acoustic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("audio_assets", "acoustic_json")
    op.drop_column("audio_assets", "acoustic_version")
    op.drop_column("audio_assets", "acoustic_completed_at")
    op.drop_column("audio_assets", "acoustic_completed")
