"""Unit tests for Celery heartbeat task."""

from unittest.mock import patch

from app.infrastructure.celery.tasks import heartbeat


def test_heartbeat_task_returns_ok() -> None:
    with patch("app.infrastructure.celery.tasks.run_async") as run_async:

        def fake_run(coro):  # type: ignore[no-untyped-def]
            if hasattr(coro, "close"):
                coro.close()
            return None

        run_async.side_effect = fake_run
        result = heartbeat.apply().get()
    assert result["status"] == "ok"
    assert result["service"] == "worker"
    assert "timestamp" in result
    assert "worker_id" in result
    run_async.assert_called_once()
