"""API tests for audio query endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.audio.schemas import (
    AudioAnalysisRead,
    AudioAssetRead,
    AudioDownloadData,
    AudioMetadataRead,
    AudioSegmentsRead,
    AudioTechnicalRead,
)
from app.shared.domain.enums import AudioStatus


@pytest.fixture
def audio_read() -> AudioAssetRead:
    now = datetime.now(timezone.utc)
    return AudioAssetRead(
        id=uuid4(),
        batch_id=uuid4(),
        filename="call.wav",
        format="wav",
        extension="wav",
        mime_type="audio/wav",
        size_bytes=1000,
        duration=1.2,
        sample_rate=44100,
        channels=2,
        storage_key="uploads/b/original/call.wav",
        normalized_storage_key="uploads/b/normalized/a.wav",
        processing_status=AudioStatus.COMPLETED,
        is_preprocessed=True,
        preprocessed_at=now,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def api_client(audio_read: AudioAssetRead) -> TestClient:
    from app.audio.dependencies import get_audio_query_service
    from app.config.settings import get_settings
    from app.infrastructure.redis.client import get_redis_client
    from app.main import create_application
    from app.shared.database.session import async_session_factory, get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    async_session_factory.cache_clear()
    get_redis_client.cache_clear()

    application = create_application()
    service = AsyncMock()
    service.get_audio = AsyncMock(return_value=audio_read)
    service.get_metadata = AsyncMock(
        return_value=AudioMetadataRead(
            audio_id=audio_read.id,
            metadata={"duration": 1.2, "normalized_sample_rate": 16000},
            is_preprocessed=True,
        )
    )
    service.get_download_url = AsyncMock(
        return_value=AudioDownloadData(
            audio_id=audio_read.id,
            url="https://example.test/signed",
            storage_key=audio_read.normalized_storage_key or audio_read.storage_key,
            content_variant="normalized",
            expires_in=3600,
        )
    )
    service.get_analysis = AsyncMock(
        return_value=AudioAnalysisRead(
            audio_id=audio_read.id,
            analysis_completed=True,
            analysis_version="1.0.0",
            analysis_storage_key="uploads/b/analysis/a.json",
            analysis={
                "vad": {
                    "speech_segments": [{"start": 0.1, "end": 0.6}],
                    "silence_segments": [{"start": 0.0, "end": 0.1}],
                    "speech_duration": 0.5,
                    "speech_ratio": 0.5,
                    "largest_silence": 0.1,
                    "speech_start": 0.1,
                    "speech_end": 0.6,
                },
                "features": {"mfcc": [0.0] * 13},
            },
        )
    )
    service.get_segments = AsyncMock(
        return_value=AudioSegmentsRead(
            audio_id=audio_read.id,
            speech_segments=[{"start": 0.1, "end": 0.6}],
            silence_segments=[{"start": 0.0, "end": 0.1}],
            speech_duration=0.5,
            speech_ratio=0.5,
            largest_silence=0.1,
            speech_start=0.1,
            speech_end=0.6,
        )
    )
    service.get_technical = AsyncMock(
        return_value=AudioTechnicalRead(
            audio_id=audio_read.id,
            audio_quality="CLEAR",
            speaker_overlap_present=False,
            long_silence_present=False,
            technical_version="1.0.0",
            technical_completed=True,
        )
    )
    application.dependency_overrides[get_audio_query_service] = lambda: service

    redis_mock = AsyncMock()
    redis_mock.connect = AsyncMock()
    redis_mock.disconnect = AsyncMock()

    with patch("app.main.get_redis_client", return_value=redis_mock):
        with TestClient(application) as client:
            yield client

    application.dependency_overrides.clear()
    get_settings.cache_clear()


def test_get_audio_metadata_download(api_client: TestClient, audio_read: AudioAssetRead) -> None:
    detail = api_client.get(f"/api/v1/audio/{audio_read.id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["is_preprocessed"] is True

    metadata = api_client.get(f"/api/v1/audio/{audio_read.id}/metadata")
    assert metadata.status_code == 200
    assert metadata.json()["data"]["metadata"]["normalized_sample_rate"] == 16000

    download = api_client.get(f"/api/v1/audio/{audio_read.id}/download")
    assert download.status_code == 200
    assert download.json()["data"]["content_variant"] == "normalized"


def test_get_analysis_and_segments(api_client: TestClient, audio_read: AudioAssetRead) -> None:
    analysis = api_client.get(f"/api/v1/audio/{audio_read.id}/analysis")
    assert analysis.status_code == 200
    body = analysis.json()["data"]
    assert body["analysis_completed"] is True
    assert "vad" in body["analysis"]

    segments = api_client.get(f"/api/v1/audio/{audio_read.id}/segments")
    assert segments.status_code == 200
    assert segments.json()["data"]["speech_ratio"] == 0.5


def test_get_technical(api_client: TestClient, audio_read: AudioAssetRead) -> None:
    response = api_client.get(f"/api/v1/audio/{audio_read.id}/technical")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["audio_quality"] == "CLEAR"
    assert body["speaker_overlap_present"] is False
    assert body["long_silence_present"] is False
    assert body["technical_version"] == "1.0.0"
    assert body["technical_completed"] is True
