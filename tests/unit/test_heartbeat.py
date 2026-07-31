"""Unit tests for Celery heartbeat task."""

from app.infrastructure.celery.tasks import heartbeat


def test_heartbeat_task_returns_ok() -> None:
    result = heartbeat.apply().get()
    assert result["status"] == "ok"
    assert result["service"] == "worker"
    assert "timestamp" in result
