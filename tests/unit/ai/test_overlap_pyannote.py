"""Unit tests for pyannote overlap detector + backend selection."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import numpy as np
import pytest

from app.ai.technical.factory import build_overlap_detector
from app.ai.technical.overlap import (
    PyannoteOverlapDetector,
    SignalBasedOverlapDetector,
)
from app.ai.technical.overlap_model import (
    get_or_load_overlap_pipeline,
    overlap_pipeline_loaded,
    reset_overlap_model_registry,
)
from app.audio.analysis.schemas import (
    SignalFeatures,
    TimeSegment,
    VADResult,
)
from app.config.settings import TechnicalSettings


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


def _settings(**overrides: Any) -> TechnicalSettings:
    base = TechnicalSettings()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class _FakeTimeline:
    def __init__(self, duration: float) -> None:
        self._duration = duration

    def duration(self) -> float:
        return self._duration


class _FakeAnnotation:
    def __init__(self, duration: float) -> None:
        self._duration = duration

    def get_timeline(self) -> _FakeTimeline:
        return _FakeTimeline(self._duration)


class _FakePipeline:
    def __init__(self, duration: float = 2.0, *, fail: bool = False) -> None:
        self.duration = duration
        self.fail = fail
        self.calls = 0

    def __call__(self, payload: dict[str, Any]) -> _FakeAnnotation:
        self.calls += 1
        if self.fail:
            raise RuntimeError("simulated pyannote failure")
        assert "waveform" in payload
        assert payload["sample_rate"] == 16000
        return _FakeAnnotation(self.duration)


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    reset_overlap_model_registry()
    yield
    reset_overlap_model_registry()


def test_factory_selects_heuristic_backend() -> None:
    detector = build_overlap_detector(_settings(overlap_backend="heuristic"))
    assert isinstance(detector, SignalBasedOverlapDetector)


def test_factory_selects_pyannote_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.ai.technical.factory.pyannote_dependency_available",
        lambda: True,
    )
    detector = build_overlap_detector(_settings(overlap_backend="pyannote"))
    assert isinstance(detector, PyannoteOverlapDetector)


def test_factory_falls_back_when_pyannote_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.ai.technical.factory.pyannote_dependency_available",
        lambda: False,
    )
    detector = build_overlap_detector(_settings(overlap_backend="pyannote"))
    assert isinstance(detector, SignalBasedOverlapDetector)


def test_protocol_compatibility_signal_and_pyannote() -> None:
    settings = _settings(overlap_threshold=0.5)
    heuristic = SignalBasedOverlapDetector(settings)
    pyannote = PyannoteOverlapDetector(
        settings,
        pipeline_factory=lambda _s: _FakePipeline(duration=0.0),
    )
    features = _features()
    vad = _vad()
    for detector in (heuristic, pyannote):
        present, score, details = detector.detect(features, vad)
        assert isinstance(present, bool)
        assert 0.0 <= score <= 1.0
        assert isinstance(details, dict)
        assert all(isinstance(v, float) for v in details.values())


def test_singleton_loading() -> None:
    settings = _settings(overlap_model_name="fake/overlap-model")
    loads = {"count": 0}

    def factory(_settings: TechnicalSettings) -> _FakePipeline:
        loads["count"] += 1
        return _FakePipeline(duration=1.0)

    first = get_or_load_overlap_pipeline(settings, pipeline_factory=factory)
    second = get_or_load_overlap_pipeline(settings, pipeline_factory=factory)
    assert first is second
    assert loads["count"] == 1
    assert overlap_pipeline_loaded(settings.overlap_model_name) is True


def test_pyannote_inference_success_uses_threshold() -> None:
    settings = _settings(overlap_threshold=0.2)
    pipeline = _FakePipeline(duration=4.0)  # 4/8 speech = 0.5
    detector = PyannoteOverlapDetector(
        settings,
        pipeline_factory=lambda _s: pipeline,
    )
    waveform = np.zeros(16000, dtype=np.float32)
    detector.bind_waveform(waveform, 16000)
    present, score, details = detector.detect(_features(), _vad(speech_duration=8.0))
    assert present is True
    assert score == pytest.approx(0.5, abs=1e-6)
    assert details["threshold"] == 0.2
    assert pipeline.calls == 1


def test_pyannote_inference_failure_falls_back_to_heuristic() -> None:
    settings = _settings(overlap_threshold=0.99)
    detector = PyannoteOverlapDetector(
        settings,
        pipeline_factory=lambda _s: _FakePipeline(fail=True),
    )
    detector.bind_waveform(np.zeros(8000, dtype=np.float32), 16000)
    present, score, details = detector.detect(_features(), _vad())
    # Heuristic on calm features should be well below 0.99.
    assert present is False
    assert score < 0.99
    assert "speech_density" in details


def test_pyannote_missing_waveform_falls_back() -> None:
    settings = _settings()
    detector = PyannoteOverlapDetector(
        settings,
        pipeline_factory=lambda _s: _FakePipeline(duration=8.0),
    )
    # No bind_waveform → heuristic path.
    present, score, details = detector.detect(_features(), _vad())
    assert "speech_density" in details
    assert 0.0 <= score <= 1.0
    assert isinstance(present, bool)


def test_overlap_threshold_from_settings() -> None:
    low = _settings(overlap_threshold=0.1)
    high = _settings(overlap_threshold=0.9)
    pipeline = _FakePipeline(duration=4.0)  # score 0.5
    low_det = PyannoteOverlapDetector(low, pipeline_factory=lambda _s: pipeline)
    high_det = PyannoteOverlapDetector(high, pipeline_factory=lambda _s: pipeline)
    wave = np.zeros(16000, dtype=np.float32)
    low_det.bind_waveform(wave, 16000)
    high_det.bind_waveform(wave.copy(), 16000)
    present_low, _, _ = low_det.detect(_features(), _vad(speech_duration=8.0))
    present_high, _, _ = high_det.detect(_features(), _vad(speech_duration=8.0))
    assert present_low is True
    assert present_high is False


@pytest.mark.asyncio
async def test_technical_service_idempotent_with_pyannote_detector() -> None:
    """Idempotency lives in TechnicalService; detector swap must not break it."""
    from datetime import datetime, timezone

    from app.ai.technical.analyzer import TechnicalAnalyzer
    from app.ai.technical.pipeline import TechnicalPipeline, technical_storage_key
    from app.ai.technical.quality import AudioQualityAnalyzer
    from app.ai.technical.schemas import TECHNICAL_VERSION
    from app.ai.technical.service import TechnicalService
    from app.ai.technical.silence import LongSilenceDetector
    from app.audio.analysis.schemas import AnalysisArtifact
    from app.audio.models import AudioAsset
    from app.shared.domain.enums import AudioStatus
    from tests.unit.ai.test_technical import FakeAssets, FakeStorage

    batch_id = uuid4()
    audio_id = uuid4()
    artifact = AnalysisArtifact(
        audio_id=str(audio_id),
        batch_id=str(batch_id),
        sample_rate=16000,
        vad=_vad(),
        features=_features(),
    )
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
        analysis_completed=True,
        analysis_json=artifact.to_storage_dict(),
    )
    asset.id = audio_id

    settings = _settings(overlap_backend="pyannote", overlap_threshold=0.5)
    pipeline_obj = _FakePipeline(duration=0.0)
    detector = PyannoteOverlapDetector(
        settings,
        pipeline_factory=lambda _s: pipeline_obj,
    )
    storage = FakeStorage()
    # Provide a tiny wav payload so optional waveform load succeeds.
    storage.objects[asset.normalized_storage_key] = b"RIFF" + b"\x00" * 64

    analyzer = TechnicalAnalyzer(
        silence=LongSilenceDetector(settings),
        quality=AudioQualityAnalyzer(settings),
        overlap=detector,
    )
    service = TechnicalService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        pipeline=TechnicalPipeline(storage=storage, analyzer=analyzer),  # type: ignore[arg-type]
    )

    first = await service.analyze_audio(asset.id)
    assert asset.technical_completed is True
    assert first.version == TECHNICAL_VERSION
    key = technical_storage_key(asset.batch_id, asset.id)
    assert key in storage.objects

    objects_before = dict(storage.objects)
    second = await service.analyze_audio(asset.id)
    assert storage.objects == objects_before
    assert second.speaker_overlap_present == first.speaker_overlap_present
