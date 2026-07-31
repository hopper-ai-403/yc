"""Add technical intelligence fields to audio_assets.

Revision ID: d1f3a7b29c05
Revises: c9a2e5f01d88
Create Date: 2026-07-31 22:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d1f3a7b29c05"
down_revision = "c9a2e5f01d88"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audio_assets",
        sa.Column(
            "technical_completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "audio_assets",
        sa.Column("technical_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column("technical_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column(
            "technical_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("audio_assets", "technical_json")
    op.drop_column("audio_assets", "technical_completed_at")
    op.drop_column("audio_assets", "technical_version")
    op.drop_column("audio_assets", "technical_completed")
