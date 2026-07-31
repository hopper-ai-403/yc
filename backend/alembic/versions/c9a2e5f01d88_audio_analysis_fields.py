"""Add audio analysis foundation columns.

Revision ID: c9a2e5f01d88
Revises: b7e4d2a91c03
Create Date: 2026-07-31 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c9a2e5f01d88"
down_revision: str | None = "b7e4d2a91c03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audio_assets",
        sa.Column(
            "analysis_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "audio_assets",
        sa.Column("analysis_storage_key", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column("analysis_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column("analysis_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column(
            "analysis_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_audio_assets_analysis_completed",
        "audio_assets",
        ["analysis_completed"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audio_assets_analysis_completed", table_name="audio_assets")
    op.drop_column("audio_assets", "analysis_json")
    op.drop_column("audio_assets", "analysis_completed_at")
    op.drop_column("audio_assets", "analysis_version")
    op.drop_column("audio_assets", "analysis_storage_key")
    op.drop_column("audio_assets", "analysis_completed")
