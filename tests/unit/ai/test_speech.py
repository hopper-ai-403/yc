"""Unit tests for Speech Intelligence Engine (Sprint 8)."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import numpy as np
import pytest

import app.shared.database.models_registry  # noqa: F401
from app.ai.speech.analyzer import SpeechAnalyzer
from app.ai.speech.exceptions import (
    SpeechArtifactMissingException,
    SpeechInferenceException,
    SpeechNotFoundException,
)
from app.ai.speech.factory import build_speech_service
from app.ai.speech.inference import (
    get_or_load_model,
    map_intensity,
    map_label,
    reset_model_registry,
)
from app.ai.speech.model import LabelScore, ModelMetadata, ModelPrediction
from app.ai.speech.pipeline import SpeechPipeline, speech_storage_key
from app.ai.speech.schemas import SPEECH_VERSION
from app.ai.speech.service import SpeechService
from app.audio.models import AudioAsset
from app.config.settings import SpeechSettings
from app.shared.domain.enums import AudioStatus, EmotionIntensity, EmotionTone


class MockSpeechEmotionModel:
    """Deterministic mock SER model for tests."""

    load_calls = 0

    def __init__(self, settings: SpeechSettings) -> None:
        self._settings = settings
        self.loaded = False

    def load(self) -> None:
        type(self).load_calls += 1
        self.loaded = True

    def predict(self, waveform: np.ndarray, sample_rate: int) -> ModelPrediction:
        if not self.loaded:
            raise SpeechInferenceException("not loaded")
        return ModelPrediction(
            scores=[
                LabelScore(label="ang", probability=0.62),
                LabelScore(label="neu", probability=0.25),
                LabelScore(label="hap", probability=0.13),
            ]
        )

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            name=self._settings.model_name,
            backend="mock",
            labels=["ang", "neu", "hap"],
        )


def _settings(**overrides: Any) -> SpeechSettings:
    base = SpeechSettings()
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

    async def save_speech_result(self, asset_id: Any, **kwargs: Any) -> AudioAsset:
        self.asset.speech_version = kwargs["speech_version"]
        self.asset.speech_json = dict(kwargs["speech_json"])
        self.asset.speech_completed = True
        self.asset.speech_completed_at = kwargs["speech_completed_at"]
        return self.asset


def _asset(storage: FakeStorage, *, with_waveform: bool = True) -> AudioAsset:
    import soundfile as sf

    batch_id = uuid4()
    audio_id = uuid4()
    normalized_key = f"uploads/{batch_id}/normalized/{audio_id}.wav"
    if with_waveform:
        sr = 16000
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        wav = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        buf = io.BytesIO()
        sf.write(buf, wav, sr, format="WAV")
        storage.objects[normalized_key] = buf.getvalue()

    asset = AudioAsset(
        batch_id=batch_id,
        filename="call.wav",
        format="wav",
        extension="wav",
        mime_type="audio/wav",
        size_bytes=1024,
        checksum_sha256="e" * 64,
        uploaded_at=datetime.now(timezone.utc),
        storage_key=f"uploads/{batch_id}/original/call.wav",
        normalized_storage_key=normalized_key if with_waveform else None,
        processing_status=AudioStatus.PROCESSING,
        is_preprocessed=with_waveform,
    )
    asset.id = audio_id
    return asset


# --- Label mapping ------------------------------------------------------


def test_label_mapping_known_labels() -> None:
    settings = _settings()
    assert map_label("ang", settings) is EmotionTone.FRUSTRATED
    assert map_label("hap", settings) is EmotionTone.SATISFIED
    assert map_label("neu", settings) is EmotionTone.NEUTRAL
    assert map_label("sad", settings) is EmotionTone.UPSET
    assert map_label("fea", settings) is EmotionTone.DISTRESSED


def test_label_mapping_unknown_fallback() -> None:
    settings = _settings(unmapped_label_tone="NEUTRAL")
    assert map_label("boredom", settings) is EmotionTone.NEUTRAL


def test_label_mapping_case_insensitive() -> None:
    settings = _settings()
    assert map_label("ANG", settings) is EmotionTone.FRUSTRATED


# --- Intensity mapping --------------------------------------------------


def test_intensity_bands() -> None:
    settings = _settings()
    assert map_intensity(0.9, settings) is EmotionIntensity.HIGH
    assert map_intensity(0.5, settings) is EmotionIntensity.MEDIUM
    assert map_intensity(0.2, settings) is EmotionIntensity.LOW


def test_intensity_thresholds_configurable() -> None:
    settings = _settings(intensity_medium_probability=0.9, intensity_high_probability=0.95)
    assert map_intensity(0.62, settings) is EmotionIntensity.LOW


# --- Singleton / model loading -----------------------------------------


def test_singleton_loads_once() -> None:
    reset_model_registry()
    MockSpeechEmotionModel.load_calls = 0
    settings = _settings(model_name="mock-model")
    first = get_or_load_model(settings, model_factory=MockSpeechEmotionModel)
    second = get_or_load_model(settings, model_factory=MockSpeechEmotionModel)
    assert first is second
    assert MockSpeechEmotionModel.load_calls == 1
    reset_model_registry()


def test_predict_before_load_raises() -> None:
    model = MockSpeechEmotionModel(_settings())
    with pytest.raises(SpeechInferenceException):
        model.predict(np.zeros(100, dtype=np.float32), 16000)


# --- Analyzer ------------------------------------------------------------


def test_analyzer_maps_tone_and_intensity() -> None:
    settings = _settings()
    model = MockSpeechEmotionModel(settings)
    model.load()
    analyzer = SpeechAnalyzer(model=model, settings=settings)
    result = analyzer.analyze(
        audio_id="a",
        batch_id="b",
        waveform=np.zeros(16000, dtype=np.float32),
        sample_rate=16000,
    )
    assert result.emotional_tone is EmotionTone.FRUSTRATED
    assert result.emotional_intensity is EmotionIntensity.MEDIUM
    assert result.raw_label == "ang"
    assert result.tone_probabilities["FRUSTRATED"] == 0.62


# --- Pipeline / service --------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_uploads_speech_json() -> None:
    pytest.importorskip("soundfile")
    storage = FakeStorage()
    asset = _asset(storage)
    settings = _settings()
    model = MockSpeechEmotionModel(settings)
    model.load()
    pipeline = SpeechPipeline(
        storage=storage,  # type: ignore[arg-type]
        analyzer=SpeechAnalyzer(model=model, settings=settings),
        settings=settings,
    )
    result = await pipeline.run(asset)
    key = speech_storage_key(asset.batch_id, asset.id)
    assert key in storage.objects
    stored = json.loads(storage.objects[key].decode("utf-8"))
    assert stored["emotional_tone"] == "FRUSTRATED"
    assert stored["emotional_intensity"] == "MEDIUM"
    assert stored["version"] == SPEECH_VERSION
    assert result.top_probability == 0.62


@pytest.mark.asyncio
async def test_service_persists_and_idempotent() -> None:
    pytest.importorskip("soundfile")
    storage = FakeStorage()
    asset = _asset(storage)
    settings = _settings()
    model = MockSpeechEmotionModel(settings)
    model.load()
    pipeline = SpeechPipeline(
        storage=storage,  # type: ignore[arg-type]
        analyzer=SpeechAnalyzer(model=model, settings=settings),
        settings=settings,
    )
    service = SpeechService(assets=FakeAssets(asset), pipeline=pipeline)  # type: ignore[arg-type]

    first = await service.analyze_audio(asset.id)
    assert asset.speech_completed is True
    assert asset.speech_json is not None
    assert speech_storage_key(asset.batch_id, asset.id) in storage.objects

    objects_before = dict(storage.objects)
    second = await service.analyze_audio(asset.id)
    assert storage.objects == objects_before
    assert second.emotional_tone == first.emotional_tone


@pytest.mark.asyncio
async def test_service_missing_waveform() -> None:
    storage = FakeStorage()
    asset = _asset(storage, with_waveform=False)
    service = SpeechService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        pipeline=SpeechPipeline(
            storage=storage,  # type: ignore[arg-type]
            analyzer=SpeechAnalyzer(
                model=MockSpeechEmotionModel(_settings()),
                settings=_settings(),
            ),
            settings=_settings(),
        ),
    )
    with pytest.raises(SpeechArtifactMissingException):
        await service.analyze_audio(asset.id)


@pytest.mark.asyncio
async def test_service_get_speech_not_found() -> None:
    storage = FakeStorage()
    asset = _asset(storage, with_waveform=False)
    service = SpeechService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        pipeline=SpeechPipeline(
            storage=storage,  # type: ignore[arg-type]
            analyzer=SpeechAnalyzer(
                model=MockSpeechEmotionModel(_settings()),
                settings=_settings(),
            ),
            settings=_settings(),
        ),
    )
    with pytest.raises(SpeechNotFoundException):
        await service.get_speech(asset.id)


def test_factory_builds_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai.speech import factory

    reset_model_registry()
    MockSpeechEmotionModel.load_calls = 0
    monkeypatch.setattr(factory, "CloudflareR2Storage", lambda *args, **kwargs: FakeStorage())
    monkeypatch.setattr(
        factory,
        "get_or_load_model",
        lambda settings: MockSpeechEmotionModel(settings),
    )
    service = build_speech_service(session=None)  # type: ignore[arg-type]
    assert isinstance(service, SpeechService)
