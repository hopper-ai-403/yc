"""API tests for system endpoints (Sprint 11)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.system.dependencies import get_system_service
from app.system.schemas import (
    BenchmarkRead,
    SystemMetricsRead,
    WorkerRead,
    WorkersRead,
)


@pytest.fixture
def api_client() -> Any:
    from app.config.settings import get_settings
    from app.infrastructure.redis.client import get_redis_client
    from app.main import create_application
    from app.shared.database.session import async_session_factory, get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    async_session_factory.cache_clear()
    get_redis_client.cache_clear()

    application = create_application()
    batch_id = uuid4()

    service = AsyncMock()
    service.get_metrics = AsyncMock(
        return_value=SystemMetricsRead(
            database=True,
            redis=True,
            r2=True,
            celery=True,
            model_loaded=True,
            worker_count=2,
            system_version="1.0.0",
            checked_at=datetime.now(timezone.utc),
        )
    )
    service.list_workers = AsyncMock(
        return_value=WorkersRead(
            worker_count=2,
            stale_count=1,
            workers=[
                WorkerRead(
                    worker_id="worker-1",
                    status="ok",
                    last_heartbeat=datetime.now(timezone.utc),
                    stale=False,
                ),
                WorkerRead(
                    worker_id="worker-2",
                    status="ok",
                    last_heartbeat=None,
                    stale=True,
                ),
            ],
        )
    )
    service.run_benchmark = AsyncMock(
        return_value=BenchmarkRead(
            batch_id=batch_id,
            total_files=10,
            successful_files=9,
            failed_files=1,
            average_latency_ms=1200.5,
            p50_latency_ms=1100.0,
            p95_latency_ms=2500.0,
            p99_latency_ms=2900.0,
            batch_duration_ms=60000.0,
            throughput_files_per_minute=9.0,
            average_confidence=0.78,
            failure_rate=0.1,
        )
    )

    application.dependency_overrides[get_system_service] = lambda: service

    redis_mock = AsyncMock()
    redis_mock.connect = AsyncMock()
    redis_mock.disconnect = AsyncMock()

    with patch("app.main.get_redis_client", return_value=redis_mock):
        with TestClient(application) as client:
            client._test_batch_id = batch_id  # type: ignore[attr-defined]
            yield client

    application.dependency_overrides.clear()
    get_settings.cache_clear()


def test_system_metrics(api_client: Any) -> None:
    response = api_client.get("/api/v1/system/metrics")
    assert response.status_code == 200
    data = response.json()["data"]
    for key in (
        "database",
        "redis",
        "r2",
        "celery",
        "model_loaded",
        "worker_count",
        "system_version",
    ):
        assert key in data
    assert data["worker_count"] == 2
    assert data["model_loaded"] is True


def test_system_workers(api_client: Any) -> None:
    response = api_client.get("/api/v1/system/workers")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["worker_count"] == 2
    assert data["stale_count"] == 1
    stale = [w for w in data["workers"] if w["stale"]]
    assert len(stale) == 1
    assert stale[0]["worker_id"] == "worker-2"


def test_system_benchmark(api_client: Any) -> None:
    batch_id = api_client._test_batch_id
    response = api_client.get(
        "/api/v1/system/benchmark",
        params={"batch_id": str(batch_id)},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    for key in (
        "average_latency_ms",
        "p50_latency_ms",
        "p95_latency_ms",
        "p99_latency_ms",
        "throughput_files_per_minute",
        "average_confidence",
        "failure_rate",
    ):
        assert key in data
    assert data["throughput_files_per_minute"] == 9.0
    assert data["failure_rate"] == 0.1
