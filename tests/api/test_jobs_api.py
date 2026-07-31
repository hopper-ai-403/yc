"""API tests for job endpoints with mocked JobService."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.jobs.schemas import JobProgressData, JobRead
from app.shared.domain.enums import JobStatus

import app.shared.database.models_registry  # noqa: F401


@pytest.fixture
def job_read() -> JobRead:
    job_id = uuid4()
    batch_id = uuid4()
    now = datetime.now(timezone.utc)
    return JobRead(
        id=job_id,
        batch_id=batch_id,
        status=JobStatus.PENDING,
        progress=0,
        retry_count=0,
        total_files=2,
        processed_files=0,
        failed_files=0,
        error_message=None,
        started_at=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def api_client(job_read: JobRead) -> TestClient:
    from app.config.settings import get_settings
    from app.infrastructure.redis.client import get_redis_client
    from app.jobs.dependencies import get_job_service
    from app.main import create_application
    from app.shared.database.session import async_session_factory, get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    async_session_factory.cache_clear()
    get_redis_client.cache_clear()

    application = create_application()

    class FakeJob:
        def __init__(self, data: JobRead) -> None:
            self.id = data.id
            self.batch_id = data.batch_id
            self.status = data.status
            self.progress = data.progress
            self.retry_count = data.retry_count
            self.total_files = data.total_files
            self.processed_files = data.processed_files
            self.failed_files = data.failed_files
            self.error_message = data.error_message
            self.started_at = data.started_at
            self.completed_at = data.completed_at
            self.created_at = data.created_at
            self.updated_at = data.updated_at

    entity = FakeJob(job_read)
    service = AsyncMock()
    service.queue_job = AsyncMock(return_value=entity)
    service.retry_job = AsyncMock(return_value=entity)
    service.cancel_job = AsyncMock(return_value=entity)
    service.get_job = AsyncMock(return_value=job_read)
    service.get_progress = AsyncMock(
        return_value=JobProgressData(
            job_id=job_read.id,
            status=job_read.status,
            total_files=job_read.total_files,
            processed_files=job_read.processed_files,
            failed_files=job_read.failed_files,
            progress_percentage=job_read.progress,
            elapsed_time_ms=None,
            retry_count=job_read.retry_count,
            error_message=None,
        )
    )
    service.list_jobs = AsyncMock(return_value=[job_read])

    application.dependency_overrides[get_job_service] = lambda: service

    redis_mock = AsyncMock()
    redis_mock.connect = AsyncMock()
    redis_mock.disconnect = AsyncMock()

    from unittest.mock import patch

    with patch("app.main.get_redis_client", return_value=redis_mock):
        with TestClient(application) as client:
            yield client

    application.dependency_overrides.clear()
    get_settings.cache_clear()


def test_start_job_endpoint(api_client: TestClient, job_read: JobRead) -> None:
    response = api_client.post(f"/api/v1/jobs/{job_read.id}/start")
    assert response.status_code == 202
    body = response.json()
    assert body["success"] is True
    assert body["data"]["queued"] is True


def test_get_job_and_progress(api_client: TestClient, job_read: JobRead) -> None:
    detail = api_client.get(f"/api/v1/jobs/{job_read.id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == str(job_read.id)

    progress = api_client.get(f"/api/v1/jobs/{job_read.id}/progress")
    assert progress.status_code == 200
    assert "progress_percentage" in progress.json()["data"]


def test_list_retry_cancel(api_client: TestClient, job_read: JobRead) -> None:
    listed = api_client.get("/api/v1/jobs")
    assert listed.status_code == 200
    assert listed.json()["data"]["count"] == 1

    retry = api_client.post(f"/api/v1/jobs/{job_read.id}/retry")
    assert retry.status_code == 202

    cancel = api_client.post(f"/api/v1/jobs/{job_read.id}/cancel")
    assert cancel.status_code == 200
