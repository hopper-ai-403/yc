"""Add audio preprocessing columns.

Revision ID: b7e4d2a91c03
Revises: a3f1c8e92b04
Create Date: 2026-07-31 22:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7e4d2a91c03"
down_revision: str | None = "a3f1c8e92b04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audio_assets",
        sa.Column(
            "is_preprocessed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "audio_assets",
        sa.Column("normalized_storage_key", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column("preprocessed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_audio_assets_is_preprocessed",
        "audio_assets",
        ["is_preprocessed"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audio_assets_is_preprocessed", table_name="audio_assets")
    op.drop_column("audio_assets", "metadata_json")
    op.drop_column("audio_assets", "preprocessed_at")
    op.drop_column("audio_assets", "normalized_storage_key")
    op.drop_column("audio_assets", "is_preprocessed")
