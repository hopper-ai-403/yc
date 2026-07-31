"""Unit tests for Technical Intelligence Engine (Sprint 6)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

import app.shared.database.models_registry  # noqa: F401
from app.ai.technical.analyzer import TechnicalAnalyzer
from app.ai.technical.exceptions import (
    TechnicalArtifactMissingException,
    TechnicalNotFoundException,
)
from app.ai.technical.factory import build_technical_service
from app.ai.technical.overlap import SignalBasedOverlapDetector
from app.ai.technical.pipeline import TechnicalPipeline, technical_storage_key
from app.ai.technical.quality import AudioQualityAnalyzer
from app.ai.technical.schemas import TECHNICAL_VERSION, TechnicalResult
from app.ai.technical.service import TechnicalService
from app.ai.technical.silence import LongSilenceDetector
from app.audio.analysis.schemas import (
    AnalysisArtifact,
    SignalFeatures,
    TimeSegment,
    VADResult,
)
from app.audio.models import AudioAsset
from app.config.settings import TechnicalSettings
from app.shared.domain.enums import AudioQuality, AudioStatus


def _features(**overrides: Any) -> SignalFeatures:
    defaults: dict[str, Any] = dict(
        duration=10.0,
        rms_energy=0.2,
        peak_amplitude=0.6,
        zero_crossing_rate=0.05,
        spectral_centroid=1800.0,
        spectral_bandwidth=2200.0,
        spectral_rolloff=4200.0,
        mfcc=[0.0] * 13,
        pitch_f0=140.0,
        tempo_estimate=120.0,
        dynamic_range=22.0,
        snr_estimate=30.0,
        sample_rate=16000,
    )
    defaults.update(overrides)
    return SignalFeatures(**defaults)


def _vad(**overrides: Any) -> VADResult:
    defaults: dict[str, Any] = dict(
        speech_segments=[TimeSegment(start=0.0, end=4.0), TimeSegment(start=5.0, end=9.0)],
        silence_segments=[TimeSegment(start=4.0, end=5.0)],
        speech_duration=8.0,
        speech_ratio=0.8,
        largest_silence=1.0,
        speech_start=0.0,
        speech_end=9.0,
    )
    defaults.update(overrides)
    return VADResult(**defaults)


def _artifact(audio_id: Any, batch_id: Any, **kw: Any) -> AnalysisArtifact:
    return AnalysisArtifact(
        audio_id=str(audio_id),
        batch_id=str(batch_id),
        sample_rate=16000,
        vad=_vad(**{k[4:]: v for k, v in kw.items() if k.startswith("vad_")}),
        features=_features(**{k[9:]: v for k, v in kw.items() if k.startswith("features_")}),
    )


def _settings(**overrides: Any) -> TechnicalSettings:
    base = TechnicalSettings()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload(self, key: str, data: bytes, **_: Any) -> str:
        self.objects[key] = data
        return key

    async def download(self, key: str) -> bytes:
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]

    async def get_signed_url(self, key: str, expires_in: int = 3600) -> str:
        return f"https://example.test/{key}"

    async def health_check(self) -> bool:
        return True


class FakeAssets:
    def __init__(self, asset: AudioAsset) -> None:
        self.asset = asset

    async def find_by_id(self, asset_id: Any) -> AudioAsset | None:
        return self.asset if self.asset.id == asset_id else None

    async def save_technical_result(self, asset_id: Any, **kwargs: Any) -> AudioAsset:
        self.asset.technical_version = kwargs["technical_version"]
        self.asset.technical_json = dict(kwargs["technical_json"])
        self.asset.technical_completed = True
        self.asset.technical_completed_at = kwargs["technical_completed_at"]
        return self.asset


def _asset(analysis_json: dict[str, Any] | None = None) -> AudioAsset:
    batch_id = uuid4()
    audio_id = uuid4()
    asset = AudioAsset(
        batch_id=batch_id,
        filename="call.wav",
        format="wav",
        extension="wav",
        mime_type="audio/wav",
        size_bytes=1024,
        checksum_sha256="c" * 64,
        uploaded_at=datetime.now(timezone.utc),
        storage_key=f"uploads/{batch_id}/original/call.wav",
        normalized_storage_key=f"uploads/{batch_id}/normalized/{audio_id}.wav",
        processing_status=AudioStatus.PROCESSING,
        is_preprocessed=True,
        analysis_completed=analysis_json is not None,
        analysis_json=analysis_json,
    )
    asset.id = audio_id
    return asset


# --- Silence detector -------------------------------------------------


def test_long_silence_by_largest_silence() -> None:
    detector = LongSilenceDetector(_settings(long_silence_seconds=5.0))
    present, details = detector.detect(_vad(largest_silence=7.5))
    assert present is True
    assert details["largest_silence_seconds"] == 7.5


def test_long_silence_by_silence_ratio() -> None:
    vad = VADResult(
        speech_segments=[TimeSegment(start=0.0, end=2.0)],
        silence_segments=[TimeSegment(start=2.0, end=10.0)],
        speech_duration=2.0,
        speech_ratio=0.2,
        largest_silence=8.0,
        speech_start=0.0,
        speech_end=2.0,
    )
    detector = LongSilenceDetector(
        _settings(long_silence_seconds=99.0, total_silence_ratio=0.5, min_speech_ratio=0.1)
    )
    present, _ = detector.detect(vad)
    assert present is True


def test_no_long_silence() -> None:
    detector = LongSilenceDetector(_settings())
    present, _ = detector.detect(_vad())
    assert present is False


# --- Quality scoring ---------------------------------------------------


def test_quality_clear_audio() -> None:
    analyzer = AudioQualityAnalyzer(_settings())
    quality, breakdown, score = analyzer.score(_features(), _vad())
    assert quality is AudioQuality.CLEAR
    assert score >= 85.0
    assert breakdown.total_penalty < 15.0


def test_quality_poor_audio() -> None:
    analyzer = AudioQualityAnalyzer(_settings())
    features = _features(snr_estimate=4.0, dynamic_range=4.0, peak_amplitude=0.999)
    vad = _vad(speech_ratio=0.1, silence_segments=[TimeSegment(start=0.0, end=9.0)])
    quality, breakdown, score = analyzer.score(features, vad)
    assert quality is AudioQuality.SEVERELY_IMPAIRED
    assert score < 65.0
    assert breakdown.total_penalty > 35.0


def test_quality_slightly_impaired() -> None:
    analyzer = AudioQualityAnalyzer(_settings())
    features = _features(snr_estimate=18.0, dynamic_range=14.0)
    vad = _vad(speech_ratio=0.55)
    quality, _, score = analyzer.score(features, vad)
    assert quality is AudioQuality.SLIGHTLY_IMPAIRED
    assert 65.0 <= score < 85.0


# --- Overlap detection -------------------------------------------------


def test_overlap_detected_high_density() -> None:
    segments = [TimeSegment(start=float(i), end=float(i) + 0.2) for i in range(0, 10)]
    vad = _vad(speech_segments=segments, speech_duration=2.0, speech_ratio=0.2)
    features = _features(zero_crossing_rate=0.18, spectral_bandwidth=4600.0, spectral_centroid=3200.0)
    detector = SignalBasedOverlapDetector(_settings(overlap_threshold=0.5))
    present, score, _ = detector.detect(features, vad)
    assert present is True
    assert score >= 0.5


def test_no_overlap_low_density() -> None:
    detector = SignalBasedOverlapDetector(_settings())
    present, score, _ = detector.detect(_features(), _vad())
    assert present is False
    assert score < 0.6


# --- Analyzer composition ----------------------------------------------


def test_analyzer_composes_outputs() -> None:
    analyzer = TechnicalAnalyzer(
        silence=LongSilenceDetector(_settings()),
        quality=AudioQualityAnalyzer(_settings()),
        overlap=SignalBasedOverlapDetector(_settings()),
    )
    result = analyzer.analyze(_artifact(uuid4(), uuid4()))
    assert result.audio_quality is AudioQuality.CLEAR
    assert result.speaker_overlap_present is False
    assert result.long_silence_present is False
    assert result.version == TECHNICAL_VERSION


# --- Pipeline / service ------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_uploads_technical_json() -> None:
    artifact = _artifact(uuid4(), uuid4())
    asset = _asset(analysis_json=artifact.to_storage_dict())
    storage = FakeStorage()
    analyzer = TechnicalAnalyzer(
        silence=LongSilenceDetector(_settings()),
        quality=AudioQualityAnalyzer(_settings()),
        overlap=SignalBasedOverlapDetector(_settings()),
    )
    pipeline = TechnicalPipeline(storage=storage, analyzer=analyzer)  # type: ignore[arg-type]
    result = await pipeline.run(asset)
    key = technical_storage_key(asset.batch_id, asset.id)
    assert key in storage.objects
    stored = json.loads(storage.objects[key].decode("utf-8"))
    assert stored["audio_quality"] == "CLEAR"
    assert stored["version"] == TECHNICAL_VERSION
    assert result.quality_breakdown.total_penalty >= 0.0


@pytest.mark.asyncio
async def test_service_persists_and_idempotent() -> None:
    artifact = _artifact(uuid4(), uuid4())
    asset = _asset(analysis_json=artifact.to_storage_dict())
    storage = FakeStorage()
    analyzer = TechnicalAnalyzer(
        silence=LongSilenceDetector(_settings()),
        quality=AudioQualityAnalyzer(_settings()),
        overlap=SignalBasedOverlapDetector(_settings()),
    )
    pipeline = TechnicalPipeline(storage=storage, analyzer=analyzer)  # type: ignore[arg-type]
    service = TechnicalService(assets=FakeAssets(asset), pipeline=pipeline)  # type: ignore[arg-type]

    first = await service.analyze_audio(asset.id)
    assert asset.technical_completed is True
    assert asset.technical_json is not None
    key = technical_storage_key(asset.batch_id, asset.id)
    assert key in storage.objects

    # Idempotent: second call returns cached payload, no re-upload.
    objects_before = dict(storage.objects)
    second = await service.analyze_audio(asset.id)
    assert storage.objects == objects_before
    assert second.audio_quality == first.audio_quality


@pytest.mark.asyncio
async def test_service_missing_artifacts() -> None:
    asset = _asset(analysis_json=None)
    service = TechnicalService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        pipeline=TechnicalPipeline(
            storage=FakeStorage(),  # type: ignore[arg-type]
            analyzer=TechnicalAnalyzer(
                silence=LongSilenceDetector(_settings()),
                quality=AudioQualityAnalyzer(_settings()),
                overlap=SignalBasedOverlapDetector(_settings()),
            ),
        ),
    )
    with pytest.raises(TechnicalArtifactMissingException):
        await service.analyze_audio(asset.id)


@pytest.mark.asyncio
async def test_service_get_technical_not_found() -> None:
    asset = _asset(analysis_json=None)
    service = TechnicalService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        pipeline=TechnicalPipeline(
            storage=FakeStorage(),  # type: ignore[arg-type]
            analyzer=TechnicalAnalyzer(
                silence=LongSilenceDetector(_settings()),
                quality=AudioQualityAnalyzer(_settings()),
                overlap=SignalBasedOverlapDetector(_settings()),
            ),
        ),
    )
    with pytest.raises(TechnicalNotFoundException):
        await service.get_technical(asset.id)


def test_factory_builds_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai.technical import factory

    monkeypatch.setattr(factory, "CloudflareR2Storage", lambda *args, **kwargs: FakeStorage())
    service = build_technical_service(session=None)  # type: ignore[arg-type]
    assert isinstance(service, TechnicalService)
