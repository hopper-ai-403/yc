"""Unit tests for Redis job progress cache."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.config.settings import JobSettings
from app.infrastructure.redis.job_progress import JobProgressCache


class FakeRedisClient:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self._client = self

    async def connect(self) -> None:
        return None

    @property
    def client(self) -> FakeRedisClient:
        return self

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                deleted += 1
        return deleted


@pytest.mark.asyncio
async def test_redis_progress_and_heartbeat_keys() -> None:
    redis = FakeRedisClient()
    settings = JobSettings(heartbeat_ttl_seconds=30, progress_ttl_seconds=120)
    cache = JobProgressCache(redis, settings)  # type: ignore[arg-type]
    job_id = uuid4()

    await cache.set_status(job_id, "RUNNING")
    await cache.set_progress(
        job_id,
        {
            "job_id": str(job_id),
            "status": "RUNNING",
            "total_files": 2,
            "processed_files": 1,
            "failed_files": 0,
            "progress_percentage": 50,
        },
    )
    await cache.set_job_heartbeat(job_id, "worker-a")
    await cache.set_worker_heartbeat("worker-a", {"status": "ok"})

    assert await cache.get_status(job_id) == "RUNNING"
    progress = await cache.get_progress(job_id)
    assert progress is not None
    assert progress["progress_percentage"] == 50
    assert redis.ttls[f"job:{job_id}:heartbeat"] == 30
    assert redis.ttls["worker:worker-a"] == 30
    assert redis.ttls[f"job:{job_id}:progress"] == 120
