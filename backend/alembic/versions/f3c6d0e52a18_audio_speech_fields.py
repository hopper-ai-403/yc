"""Add speech intelligence fields to audio_assets.

Revision ID: f3c6d0e52a18
Revises: e2b5c9d41f07
Create Date: 2026-07-31 23:15:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f3c6d0e52a18"
down_revision = "e2b5c9d41f07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audio_assets",
        sa.Column(
            "speech_completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "audio_assets",
        sa.Column("speech_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column("speech_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column(
            "speech_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("audio_assets", "speech_json")
    op.drop_column("audio_assets", "speech_version")
    op.drop_column("audio_assets", "speech_completed_at")
    op.drop_column("audio_assets", "speech_completed")
