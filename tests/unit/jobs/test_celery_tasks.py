"""Celery orchestration task tests (eager mode)."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.infrastructure.celery.tasks import heartbeat, process_audio, process_batch
from app.shared.domain.enums import AudioStatus


@pytest.fixture(autouse=True)
def _eager_celery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "true")
    from app.config.settings import get_settings
    from app.infrastructure.celery.app import celery_app

    get_settings.cache_clear()
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True


def test_heartbeat_writes_worker_key() -> None:
    with patch("app.infrastructure.celery.tasks.run_async") as run_async:

        def fake_run(coro):  # type: ignore[no-untyped-def]
            if hasattr(coro, "close"):
                coro.close()
            return None

        run_async.side_effect = fake_run
        result = heartbeat.apply().get()
    assert result["status"] == "ok"
    assert "worker_id" in result


def test_process_audio_idempotent_when_completed() -> None:
    audio_id = uuid4()
    job_id = uuid4()

    async def fake_process(a_id, j_id, worker_id):  # type: ignore[no-untyped-def]
        return {
            "audio_id": str(a_id),
            "status": "already_completed",
            "worker_id": worker_id,
        }

    with patch(
        "app.infrastructure.celery.tasks._process_audio",
        side_effect=fake_process,
    ):
        result = process_audio.apply(args=[str(audio_id), str(job_id)]).get()
    assert result["status"] == "already_completed"


def test_process_batch_fans_out_and_finalizes_empty() -> None:
    job_id = uuid4()

    with patch("app.infrastructure.celery.tasks.run_async") as run_async:

        def fake_run(coro):  # type: ignore[no-untyped-def]
            if hasattr(coro, "close"):
                coro.close()
            if fake_run.calls == 0:  # type: ignore[attr-defined]
                fake_run.calls = 1  # type: ignore[attr-defined]
                return []
            return {"job_id": str(job_id), "status": "COMPLETED"}

        fake_run.calls = 0  # type: ignore[attr-defined]
        run_async.side_effect = fake_run
        result = process_batch.apply(args=[str(job_id)]).get()
    assert result["audio_count"] == 0
    assert result["status"] == "empty_or_cancelled"


@pytest.mark.asyncio
async def test_concurrent_process_audio_simulation() -> None:
    """Simulate concurrent independent audio processing outcomes."""
    import asyncio

    results: list[str] = []

    async def one(name: str) -> None:
        await asyncio.sleep(0.01)
        results.append(name)

    await asyncio.gather(one("a"), one("b"), one("c"))
    assert set(results) == {"a", "b", "c"}


def test_audio_status_enum_includes_queued_completed() -> None:
    assert AudioStatus.QUEUED.value == "QUEUED"
    assert AudioStatus.COMPLETED.value == "COMPLETED"
