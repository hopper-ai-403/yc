"""Add prediction engine fields to predictions.

Revision ID: a4d7e1f63b29
Revises: f3c6d0e52a18
Create Date: 2026-07-31 23:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a4d7e1f63b29"
down_revision = "f3c6d0e52a18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("prediction_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("prediction_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column("prediction_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "predictions",
        sa.Column(
            "internal_prediction_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "predictions",
        sa.Column(
            "confidence_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("predictions", "confidence_breakdown")
    op.drop_column("predictions", "internal_prediction_json")
    op.drop_column("predictions", "prediction_json")
    op.drop_column("predictions", "prediction_completed_at")
    op.drop_column("predictions", "prediction_version")
