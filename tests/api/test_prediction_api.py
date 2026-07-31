"""API tests for prediction endpoints (Sprint 9)."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.prediction.dependencies import (
    get_prediction_export_service,
    get_prediction_service,
)
from app.prediction.schemas import PredictionRead

PUBLIC_PREDICTION = {
    "emotional_tone": "NEUTRAL",
    "emotional_intensity": "LOW",
    "background_noise_present": False,
    "background_noise_type": "NONE",
    "background_noise_severity": "NONE",
    "audio_quality": "CLEAR",
    "speaker_overlap_present": False,
    "long_silence_present": False,
    "confidence": 0.82,
}


@pytest.fixture
def api_client() -> TestClient:
    from app.config.settings import get_settings
    from app.infrastructure.redis.client import get_redis_client
    from app.main import create_application
    from app.shared.database.session import async_session_factory, get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    async_session_factory.cache_clear()
    get_redis_client.cache_clear()

    application = create_application()

    audio_id = uuid4()
    service = AsyncMock()
    service.get_prediction = AsyncMock(
        return_value=PredictionRead(
            audio_id=str(audio_id),
            prediction_version="1.0.0",
            prediction=dict(PUBLIC_PREDICTION),
        )
    )
    service.list_by_batch = AsyncMock(
        return_value=[
            PredictionRead(
                audio_id=str(audio_id),
                prediction_version="1.0.0",
                prediction=dict(PUBLIC_PREDICTION),
            )
        ]
    )
    service.list_by_job = AsyncMock(
        return_value=[
            PredictionRead(
                audio_id=str(audio_id),
                prediction_version="1.0.0",
                prediction=dict(PUBLIC_PREDICTION),
            )
        ]
    )

    export = AsyncMock()
    export.export_json = AsyncMock(
        return_value=[{"filename": "call.wav", "result": dict(PUBLIC_PREDICTION)}]
    )

    application.dependency_overrides[get_prediction_service] = lambda: service
    application.dependency_overrides[get_prediction_export_service] = lambda: export

    redis_mock = AsyncMock()
    redis_mock.connect = AsyncMock()
    redis_mock.disconnect = AsyncMock()

    from unittest.mock import patch

    with patch("app.main.get_redis_client", return_value=redis_mock):
        with TestClient(application) as client:
            yield client

    application.dependency_overrides.clear()
    get_settings.cache_clear()


def test_get_audio_prediction(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/audio/{uuid4()}/prediction")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["prediction_version"] == "1.0.0"
    assert set(data["prediction"].keys()) == set(PUBLIC_PREDICTION.keys())
    assert data["prediction"]["confidence"] == 0.82


def test_get_batch_predictions(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/batches/{uuid4()}/predictions")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count"] == 1
    assert set(data["predictions"][0]["prediction"].keys()) == set(
        PUBLIC_PREDICTION.keys()
    )


def test_get_job_predictions(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/jobs/{uuid4()}/predictions")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count"] == 1


def test_export_batch_predictions_json(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/batches/{uuid4()}/predictions/export.json")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count"] == 1
    result = data["results"][0]["result"]
    assert set(result.keys()) == set(PUBLIC_PREDICTION.keys())
