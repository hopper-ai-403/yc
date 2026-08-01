"""Unit tests for Acoustic Intelligence Engine (Sprint 7)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

import app.shared.database.models_registry  # noqa: F401
from app.ai.acoustic.analyzer import AcousticAnalyzer
from app.ai.acoustic.classifier import HeuristicNoiseClassifier
from app.ai.acoustic.detector import SignalBasedNoiseDetector
from app.ai.acoustic.exceptions import (
    AcousticArtifactMissingException,
    AcousticNotFoundException,
)
from app.ai.acoustic.factory import build_acoustic_service
from app.ai.acoustic.pipeline import AcousticPipeline, acoustic_storage_key
from app.ai.acoustic.schemas import ACOUSTIC_VERSION, AcousticResult
from app.ai.acoustic.service import AcousticService
from app.ai.acoustic.severity import DeterministicSeverityEstimator
from app.audio.analysis.schemas import (
    AnalysisArtifact,
    SignalFeatures,
    TimeSegment,
    VADResult,
)
from app.audio.models import AudioAsset
from app.config.settings import AcousticSettings
from app.shared.domain.enums import AudioStatus, NoiseSeverity, NoiseType


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
        speech_segments=[
            TimeSegment(start=0.0, end=4.0),
            TimeSegment(start=5.0, end=9.0),
        ],
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
        features=_features(
            **{k[9:]: v for k, v in kw.items() if k.startswith("features_")}
        ),
    )


def _settings(**overrides: Any) -> AcousticSettings:
    base = AcousticSettings()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _analyzer(settings: AcousticSettings | None = None) -> AcousticAnalyzer:
    s = settings or _settings()
    return AcousticAnalyzer(
        detector=SignalBasedNoiseDetector(s),
        classifier=HeuristicNoiseClassifier(s),
        severity=DeterministicSeverityEstimator(s),
    )


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

    async def generate_signed_url(self, key: str, expires_in: int = 3600) -> str:
        return f"https://example.test/{key}"

    async def health_check(self) -> bool:
        return True


class FakeAssets:
    def __init__(self, asset: AudioAsset) -> None:
        self.asset = asset

    async def find_by_id(self, asset_id: Any) -> AudioAsset | None:
        return self.asset if self.asset.id == asset_id else None

    async def save_acoustic_result(self, asset_id: Any, **kwargs: Any) -> AudioAsset:
        self.asset.acoustic_version = kwargs["acoustic_version"]
        self.asset.acoustic_json = dict(kwargs["acoustic_json"])
        self.asset.acoustic_completed = True
        self.asset.acoustic_completed_at = kwargs["acoustic_completed_at"]
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
        checksum_sha256="d" * 64,
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


# --- Detection ---------------------------------------------------------


def test_noise_absent_clean_signal() -> None:
    settings = _settings()
    detector = SignalBasedNoiseDetector(settings)
    present, score, _ = detector.detect(_features(), _vad())
    assert present is False
    assert score < settings.noise_presence_score_threshold


def test_noise_present_low_snr() -> None:
    settings = _settings()
    detector = SignalBasedNoiseDetector(settings)
    features = _features(
        snr_estimate=8.0, zero_crossing_rate=0.15, spectral_bandwidth=4500.0
    )
    present, score, _ = detector.detect(features, _vad())
    assert present is True
    assert score >= settings.noise_presence_score_threshold


# --- Classification ----------------------------------------------------


def test_classify_music() -> None:
    classifier = HeuristicNoiseClassifier(_settings())
    features = _features(spectral_centroid=3000.0, spectral_rolloff=6500.0)
    noise_type, _ = classifier.classify(features, _vad())
    assert noise_type is NoiseType.MUSIC


def test_classify_static() -> None:
    classifier = HeuristicNoiseClassifier(_settings())
    features = _features(zero_crossing_rate=0.2)
    noise_type, _ = classifier.classify(features, _vad())
    assert noise_type is NoiseType.STATIC


def test_classify_traffic() -> None:
    classifier = HeuristicNoiseClassifier(_settings())
    features = _features(spectral_centroid=600.0, spectral_rolloff=1500.0)
    noise_type, _ = classifier.classify(features, _vad())
    assert noise_type is NoiseType.TRAFFIC


def test_classify_other_default() -> None:
    classifier = HeuristicNoiseClassifier(_settings())
    noise_type, _ = classifier.classify(_features(), _vad())
    assert noise_type is NoiseType.OTHER


# --- Severity ----------------------------------------------------------


def test_severity_low() -> None:
    estimator = DeterministicSeverityEstimator(_settings())
    severity, _ = estimator.estimate(_features(snr_estimate=20.0), _vad(), 0.55)
    assert severity is NoiseSeverity.LOW


def test_severity_medium() -> None:
    estimator = DeterministicSeverityEstimator(_settings())
    severity, _ = estimator.estimate(
        _features(snr_estimate=14.0), _vad(speech_ratio=0.6), 0.7
    )
    assert severity is NoiseSeverity.MEDIUM


def test_severity_high() -> None:
    estimator = DeterministicSeverityEstimator(_settings())
    severity, _ = estimator.estimate(
        _features(snr_estimate=3.0), _vad(speech_ratio=0.3), 0.9
    )
    assert severity is NoiseSeverity.HIGH


# --- Business rules ----------------------------------------------------


def test_business_rule_no_noise_forces_none() -> None:
    bad = AcousticResult(
        audio_id=str(uuid4()),
        batch_id=str(uuid4()),
        background_noise_present=False,
        background_noise_type=NoiseType.MUSIC,
        background_noise_severity=NoiseSeverity.HIGH,
        noise_score=0.1,
    )
    fixed = AcousticService._enforce_business_rules(bad)
    assert fixed.background_noise_type is NoiseType.NONE
    assert fixed.background_noise_severity is NoiseSeverity.NONE


def test_business_rule_present_noise_untouched() -> None:
    good = AcousticResult(
        audio_id=str(uuid4()),
        batch_id=str(uuid4()),
        background_noise_present=True,
        background_noise_type=NoiseType.TRAFFIC,
        background_noise_severity=NoiseSeverity.MEDIUM,
        noise_score=0.8,
    )
    assert AcousticService._enforce_business_rules(good) is good


def test_analyzer_no_noise_produces_none() -> None:
    result = _analyzer().analyze(_artifact(uuid4(), uuid4()))
    assert result.background_noise_present is False
    assert result.background_noise_type is NoiseType.NONE
    assert result.background_noise_severity is NoiseSeverity.NONE


# --- Pipeline / service ------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_uploads_acoustic_json() -> None:
    artifact = _artifact(uuid4(), uuid4())
    asset = _asset(analysis_json=artifact.to_storage_dict())
    storage = FakeStorage()
    pipeline = AcousticPipeline(storage=storage, analyzer=_analyzer())  # type: ignore[arg-type]
    await pipeline.run(asset)
    key = acoustic_storage_key(asset.batch_id, asset.id)
    assert key in storage.objects
    stored = json.loads(storage.objects[key].decode("utf-8"))
    assert stored["background_noise_type"] == "NONE"
    assert stored["version"] == ACOUSTIC_VERSION


@pytest.mark.asyncio
async def test_service_persists_and_idempotent() -> None:
    artifact = _artifact(uuid4(), uuid4())
    asset = _asset(analysis_json=artifact.to_storage_dict())
    storage = FakeStorage()
    pipeline = AcousticPipeline(storage=storage, analyzer=_analyzer())  # type: ignore[arg-type]
    service = AcousticService(assets=FakeAssets(asset), pipeline=pipeline)  # type: ignore[arg-type]

    first = await service.analyze_audio(asset.id)
    assert asset.acoustic_completed is True
    assert asset.acoustic_json is not None
    assert acoustic_storage_key(asset.batch_id, asset.id) in storage.objects

    objects_before = dict(storage.objects)
    second = await service.analyze_audio(asset.id)
    assert storage.objects == objects_before
    assert second.background_noise_type == first.background_noise_type


@pytest.mark.asyncio
async def test_service_missing_artifacts() -> None:
    asset = _asset(analysis_json=None)
    service = AcousticService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        pipeline=AcousticPipeline(storage=FakeStorage(), analyzer=_analyzer()),  # type: ignore[arg-type]
    )
    with pytest.raises(AcousticArtifactMissingException):
        await service.analyze_audio(asset.id)


@pytest.mark.asyncio
async def test_service_get_acoustic_not_found() -> None:
    asset = _asset(analysis_json=None)
    service = AcousticService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        pipeline=AcousticPipeline(storage=FakeStorage(), analyzer=_analyzer()),  # type: ignore[arg-type]
    )
    with pytest.raises(AcousticNotFoundException):
        await service.get_acoustic(asset.id)


def test_factory_builds_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai.acoustic import factory

    monkeypatch.setattr(
        factory, "CloudflareR2Storage", lambda *args, **kwargs: FakeStorage()
    )
    service = build_acoustic_service(session=None)  # type: ignore[arg-type]
    assert isinstance(service, AcousticService)
