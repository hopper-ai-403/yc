"""add_audio_asset_upload_metadata

Revision ID: df8009a29616
Revises: ce21a1451fc6
Create Date: 2026-07-31 21:36:04.402356
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "df8009a29616"
down_revision: str | None = "ce21a1451fc6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audio_assets",
        sa.Column("extension", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column("mime_type", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "audio_assets",
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute("""
        UPDATE audio_assets
        SET
            extension = COALESCE(NULLIF(format, ''), 'unknown'),
            mime_type = 'application/octet-stream',
            size_bytes = 0,
            checksum_sha256 = REPEAT('0', 64),
            uploaded_at = created_at
        """)

    op.alter_column("audio_assets", "extension", nullable=False)
    op.alter_column("audio_assets", "mime_type", nullable=False)
    op.alter_column("audio_assets", "size_bytes", nullable=False)
    op.alter_column("audio_assets", "checksum_sha256", nullable=False)
    op.alter_column("audio_assets", "uploaded_at", nullable=False)


def downgrade() -> None:
    op.drop_column("audio_assets", "uploaded_at")
    op.drop_column("audio_assets", "checksum_sha256")
    op.drop_column("audio_assets", "size_bytes")
    op.drop_column("audio_assets", "mime_type")
    op.drop_column("audio_assets", "extension")
