"""Add job progress counters and audio QUEUED/COMPLETED statuses.

Revision ID: a3f1c8e92b04
Revises: df8009a29616
Create Date: 2026-07-31 22:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f1c8e92b04"
down_revision: str | None = "df8009a29616"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE audio_status ADD VALUE IF NOT EXISTS 'QUEUED'")
        op.execute("ALTER TYPE audio_status ADD VALUE IF NOT EXISTS 'COMPLETED'")

    op.add_column(
        "jobs",
        sa.Column(
            "total_files",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "processed_files",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "failed_files",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("error_message", sa.String(length=1024), nullable=True),
    )
    op.create_check_constraint(
        "ck_jobs_total_files_nonnegative",
        "jobs",
        "total_files >= 0",
    )
    op.create_check_constraint(
        "ck_jobs_processed_files_nonnegative",
        "jobs",
        "processed_files >= 0",
    )
    op.create_check_constraint(
        "ck_jobs_failed_files_nonnegative",
        "jobs",
        "failed_files >= 0",
    )

    # Backfill total_files from related batches where possible.
    op.execute("""
        UPDATE jobs AS j
        SET total_files = b.total_files
        FROM audio_batches AS b
        WHERE j.batch_id = b.id
        """)


def downgrade() -> None:
    op.drop_constraint("ck_jobs_failed_files_nonnegative", "jobs", type_="check")
    op.drop_constraint("ck_jobs_processed_files_nonnegative", "jobs", type_="check")
    op.drop_constraint("ck_jobs_total_files_nonnegative", "jobs", type_="check")
    op.drop_column("jobs", "error_message")
    op.drop_column("jobs", "failed_files")
    op.drop_column("jobs", "processed_files")
    op.drop_column("jobs", "total_files")
    # PostgreSQL cannot easily remove enum values; leave QUEUED/COMPLETED in place.
