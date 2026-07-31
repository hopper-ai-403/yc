"""Tests ensuring the initial Alembic migration artifact exists and is valid."""

from pathlib import Path


def test_initial_migration_file_exists() -> None:
    versions = Path(__file__).resolve().parents[3] / "backend" / "alembic" / "versions"
    migrations = list(versions.glob("*_initial_domain_schema.py"))
    assert migrations, "Expected initial_domain_schema Alembic revision"
    content = migrations[0].read_text(encoding="utf-8")
    for table in (
        "users",
        "audio_batches",
        "audio_assets",
        "jobs",
        "predictions",
        "audit_logs",
    ):
        assert table in content
