"""API tests for evaluation endpoints (Sprint 10)."""

from __future__ import annotations

import csv as csv_module
import io as io_module
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.evaluation.dependencies import get_evaluation_service
from app.evaluation.exceptions import (
    BatchNotFoundForEvaluationException,
    ExportNotFoundException,
)
from app.evaluation.schemas import (
    BatchExportItem,
    BatchExportsRead,
    BatchMetricsRead,
    BatchRunRead,
    BatchStatusRead,
)

ASSESSMENT_KEYS = {
    "emotional_tone",
    "emotional_intensity",
    "background_noise_present",
    "background_noise_type",
    "background_noise_severity",
    "audio_quality",
    "speaker_overlap_present",
    "long_silence_present",
    "confidence",
}

PUBLIC_RESULT = {
    "emotional_tone": "CALM",
    "emotional_intensity": "MEDIUM",
    "background_noise_present": True,
    "background_noise_type": "TRAFFIC",
    "background_noise_severity": "LOW",
    "audio_quality": "CLEAR",
    "speaker_overlap_present": False,
    "long_silence_present": True,
    "confidence": 0.75,
}


def _csv_text() -> str:
    buffer = io_module.StringIO()
    writer = csv_module.writer(buffer)
    writer.writerow(["filename", "result_json"])
    writer.writerow(["call.wav", json.dumps(PUBLIC_RESULT)])
    return buffer.getvalue()


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
    job_id = uuid4()

    service = AsyncMock()
    service.run_batch = AsyncMock(
        side_effect=lambda bid: (
            BatchRunRead(
                batch_id=bid,
                job_id=job_id,
                status="QUEUED",
                queued=True,
                already_running=False,
            )
            if bid == batch_id
            else (_raise(BatchNotFoundForEvaluationException(bid)))
        )
    )
    service.get_status = AsyncMock(
        return_value=BatchStatusRead(
            batch_id=batch_id,
            job_id=job_id,
            status="RUNNING",
            progress=60,
            total_files=5,
            processed_files=3,
            failed_files=1,
            started_at=datetime.now(timezone.utc) - timedelta(seconds=60),
            completed_at=None,
            estimated_remaining_seconds=40.0,
        )
    )
    service.export_csv = AsyncMock(return_value=_csv_text())
    service.export_json = AsyncMock(
        return_value=[{"filename": "call.wav", "result": dict(PUBLIC_RESULT)}]
    )
    service.get_metrics = AsyncMock(
        return_value=BatchMetricsRead(
            batch_id=batch_id,
            total_audio=5,
            successful_predictions=4,
            failed_predictions=1,
            success_rate=0.8,
            average_processing_time_ms=2500.5,
            min_processing_time_ms=900.0,
            max_processing_time_ms=6100.0,
            average_confidence=0.76,
            computed_at=datetime.now(timezone.utc),
        )
    )
    service.get_exports = AsyncMock(
        side_effect=lambda bid: (
            BatchExportsRead(
                batch_id=bid,
                exports=[
                    BatchExportItem(
                        name="results.csv",
                        storage_key=f"uploads/{bid}/exports/results.csv",
                        url="https://signed.example.test/results.csv?exp=3600",
                        expires_in=3600,
                    ),
                    BatchExportItem(
                        name="results.json",
                        storage_key=f"uploads/{bid}/exports/results.json",
                        url="https://signed.example.test/results.json?exp=3600",
                        expires_in=3600,
                    ),
                ],
            )
            if bid == batch_id
            else (_raise(ExportNotFoundException(bid)))
        )
    )

    application.dependency_overrides[get_evaluation_service] = lambda: service

    redis_mock = AsyncMock()
    redis_mock.connect = AsyncMock()
    redis_mock.disconnect = AsyncMock()

    with patch("app.main.get_redis_client", return_value=redis_mock):
        with TestClient(application) as client:
            client._test_batch_id = batch_id  # type: ignore[attr-defined]
            yield client

    application.dependency_overrides.clear()
    get_settings.cache_clear()


def _raise(exc: Exception) -> Any:
    raise exc


def test_run_batch(api_client: Any) -> None:
    batch_id = api_client._test_batch_id
    response = api_client.post(f"/api/v1/batches/{batch_id}/run")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["queued"] is True
    assert body["data"]["status"] == "QUEUED"


def test_run_batch_not_found(api_client: Any) -> None:
    response = api_client.post(f"/api/v1/batches/{uuid4()}/run")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BATCH_NOT_FOUND"


def test_batch_status(api_client: Any) -> None:
    batch_id = api_client._test_batch_id
    response = api_client.get(f"/api/v1/batches/{batch_id}/status")
    assert response.status_code == 200
    data = response.json()["data"]
    for key in (
        "batch_id",
        "job_id",
        "status",
        "progress",
        "total_files",
        "processed_files",
        "failed_files",
        "started_at",
        "completed_at",
        "estimated_remaining_seconds",
    ):
        assert key in data
    assert data["progress"] == 60
    assert data["estimated_remaining_seconds"] == 40.0


def test_export_csv(api_client: Any) -> None:
    batch_id = api_client._test_batch_id
    response = api_client.get(f"/api/v1/batches/{batch_id}/export/csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    parsed = list(csv_module.reader(io_module.StringIO(response.text)))
    assert parsed[0] == ["filename", "result_json"]
    result = json.loads(parsed[1][1])
    assert set(result.keys()) == ASSESSMENT_KEYS


def test_export_json(api_client: Any) -> None:
    batch_id = api_client._test_batch_id
    response = api_client.get(f"/api/v1/batches/{batch_id}/export/json")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count"] == 1
    assert set(data["results"][0]["result"].keys()) == ASSESSMENT_KEYS


def test_metrics(api_client: Any) -> None:
    batch_id = api_client._test_batch_id
    response = api_client.get(f"/api/v1/batches/{batch_id}/metrics")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_audio"] == 5
    assert data["successful_predictions"] == 4
    assert data["failed_predictions"] == 1
    assert data["success_rate"] == 0.8
    assert data["average_processing_time_ms"] == 2500.5
    assert data["average_confidence"] == 0.76


def test_exports_signed_urls(api_client: Any) -> None:
    batch_id = api_client._test_batch_id
    response = api_client.get(f"/api/v1/batches/{batch_id}/exports")
    assert response.status_code == 200
    exports = response.json()["data"]["exports"]
    assert {item["name"] for item in exports} == {"results.csv", "results.json"}
    assert all(
        item["url"].startswith("https://signed.example.test/") for item in exports
    )


def test_exports_not_found(api_client: Any) -> None:
    response = api_client.get(f"/api/v1/batches/{uuid4()}/exports")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXPORT_NOT_FOUND"
