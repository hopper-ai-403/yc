"""Unit tests for segmentation, VAD (energy), features, and analysis service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import numpy as np
import pytest

import app.shared.database.models_registry  # noqa: F401
from app.audio.analysis.exceptions import InvalidWaveformException
from app.audio.analysis.features import FeatureExtractor
from app.audio.analysis.pipeline import AnalysisPipeline, analysis_storage_key
from app.audio.analysis.schemas import ANALYSIS_VERSION, AnalysisArtifact, TimeSegment
from app.audio.analysis.segmentation import build_vad_result
from app.audio.analysis.service import AnalysisService
from app.audio.analysis.signal import load_waveform
from app.audio.analysis.vad import EnergyVAD
from app.audio.models import AudioAsset
from app.config.settings import AnalysisSettings
from app.shared.domain.enums import AudioStatus


def test_speech_and_silence_segmentation() -> None:
    result = build_vad_result(
        [TimeSegment(start=0.5, end=1.5), TimeSegment(start=2.0, end=2.5)],
        total_duration=3.0,
    )
    assert result.speech_duration == pytest.approx(1.5)
    assert result.speech_ratio == pytest.approx(0.5)
    assert result.speech_start == 0.5
    assert result.speech_end == 2.5
    assert result.largest_silence == pytest.approx(0.5)
    assert len(result.silence_segments) == 3


def test_energy_vad_detects_speech_and_silence() -> None:
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    speech = 0.2 * np.sin(2 * np.pi * 220 * t)
    silence = np.zeros(sr // 2, dtype=np.float32)
    waveform = np.concatenate([silence, speech.astype(np.float32), silence])
    vad = EnergyVAD(threshold_ratio=0.05)
    result = vad.detect(waveform, sr)
    assert result.speech_duration > 0.5
    assert result.speech_ratio > 0.3
    assert result.largest_silence > 0.2


def test_feature_extraction_on_tone() -> None:
    librosa = pytest.importorskip("librosa")
    del librosa
    sr = 16000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    waveform = (0.3 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)
    vad = EnergyVAD().detect(waveform, sr)
    features = FeatureExtractor().extract(waveform, sr, vad=vad)
    assert features.duration == pytest.approx(0.5, abs=0.01)
    assert features.peak_amplitude > 0
    assert len(features.mfcc) == 13
    assert features.sample_rate == sr
    assert features.dynamic_range >= 0


def test_load_waveform_rejects_silent() -> None:
    import io

    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, np.zeros(1600, dtype=np.float32), 16000, format="WAV")
    with pytest.raises(InvalidWaveformException):
        load_waveform(buf.getvalue(), expected_sample_rate=16000)


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload(self, key: str, data: bytes, **kwargs: Any) -> str:
        del kwargs
        self.objects[key] = data if isinstance(data, bytes) else bytes(data)
        return key

    async def download(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def list(self, prefix: str = "", *, max_keys: int = 1000) -> list[str]:
        return [k for k in self.objects if k.startswith(prefix)][:max_keys]

    async def generate_signed_url(self, key: str, **kwargs: Any) -> str:
        return f"https://example.test/{key}"

    async def health_check(self) -> bool:
        return True


class FakeAssets:
    def __init__(self, asset: AudioAsset) -> None:
        self.asset = asset

    async def find_by_id(self, asset_id: Any) -> AudioAsset | None:
        return self.asset if self.asset.id == asset_id else None

    async def create(self, asset: AudioAsset) -> AudioAsset:
        self.asset = asset
        return asset

    async def find_by_batch(self, batch_id: Any) -> list[AudioAsset]:
        return [self.asset]

    async def update_status(self, asset_id: Any, status: AudioStatus) -> AudioAsset:
        self.asset.processing_status = status
        return self.asset

    async def save_preprocessing_result(
        self, asset_id: Any, **kwargs: Any
    ) -> AudioAsset:
        return self.asset

    async def save_analysis_result(self, asset_id: Any, **kwargs: Any) -> AudioAsset:
        self.asset.analysis_storage_key = kwargs["analysis_storage_key"]
        self.asset.analysis_version = kwargs["analysis_version"]
        self.asset.analysis_json = dict(kwargs["analysis_json"])
        self.asset.analysis_completed = True
        self.asset.analysis_completed_at = kwargs["analysis_completed_at"]
        return self.asset


def _asset_with_normalized(storage: FakeStorage) -> AudioAsset:
    import io

    import soundfile as sf

    batch_id = uuid4()
    audio_id = uuid4()
    sr = 16000
    t = np.linspace(0, 0.4, int(sr * 0.4), endpoint=False)
    wav = (0.25 * np.sin(2 * np.pi * 200 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, wav, sr, format="WAV")
    key = f"uploads/{batch_id}/normalized/{audio_id}.wav"
    storage.objects[key] = buf.getvalue()

    asset = AudioAsset(
        batch_id=batch_id,
        filename="call.wav",
        format="wav",
        extension="wav",
        mime_type="audio/wav",
        size_bytes=len(buf.getvalue()),
        checksum_sha256="b" * 64,
        uploaded_at=datetime.now(timezone.utc),
        storage_key=f"uploads/{batch_id}/original/call.wav",
        normalized_storage_key=key,
        processing_status=AudioStatus.PROCESSING,
        is_preprocessed=True,
        analysis_completed=False,
    )
    asset.id = audio_id
    return asset


@pytest.mark.asyncio
async def test_analysis_pipeline_persists_to_r2() -> None:
    pytest.importorskip("librosa")
    pytest.importorskip("soundfile")
    storage = FakeStorage()
    asset = _asset_with_normalized(storage)
    pipeline = AnalysisPipeline(
        settings=AnalysisSettings(vad_backend="energy", timeout_seconds=60),
        storage=storage,  # type: ignore[arg-type]
        vad=EnergyVAD(),
        features=FeatureExtractor(),
    )
    artifact = await pipeline.run(asset)
    key = analysis_storage_key(asset.batch_id, asset.id)
    assert key in storage.objects
    assert artifact.version == ANALYSIS_VERSION
    assert len(artifact.features.mfcc) == 13


@pytest.mark.asyncio
async def test_analysis_service_idempotency() -> None:
    from app.audio.analysis.schemas import SignalFeatures, VADResult

    storage = FakeStorage()
    asset = _asset_with_normalized(storage)
    asset.analysis_completed = True
    asset.analysis_storage_key = analysis_storage_key(asset.batch_id, asset.id)
    asset.analysis_version = ANALYSIS_VERSION
    asset.analysis_json = AnalysisArtifact(
        audio_id=str(asset.id),
        batch_id=str(asset.batch_id),
        sample_rate=16000,
        vad=VADResult(
            speech_segments=[],
            silence_segments=[TimeSegment(start=0.0, end=1.0)],
            speech_duration=0.0,
            speech_ratio=0.0,
            largest_silence=1.0,
        ),
        features=SignalFeatures(
            duration=1.0,
            rms_energy=0.1,
            peak_amplitude=0.2,
            zero_crossing_rate=0.1,
            spectral_centroid=1000.0,
            spectral_bandwidth=1000.0,
            spectral_rolloff=2000.0,
            mfcc=[0.0] * 13,
            pitch_f0=None,
            tempo_estimate=None,
            dynamic_range=6.0,
            snr_estimate=None,
            sample_rate=16000,
        ),
    ).to_storage_dict()

    class BoomPipeline:
        async def run(self, _asset: AudioAsset) -> AnalysisArtifact:
            raise AssertionError("should not run")

    service = AnalysisService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        pipeline=BoomPipeline(),  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
    )
    result = await service.analyze_audio(asset.id)
    assert result.audio_id == str(asset.id)


@pytest.mark.asyncio
async def test_analysis_service_persists() -> None:
    pytest.importorskip("librosa")
    pytest.importorskip("soundfile")
    storage = FakeStorage()
    asset = _asset_with_normalized(storage)
    assets = FakeAssets(asset)
    service = AnalysisService(
        assets=assets,  # type: ignore[arg-type]
        pipeline=AnalysisPipeline(
            settings=AnalysisSettings(vad_backend="energy"),
            storage=storage,  # type: ignore[arg-type]
            vad=EnergyVAD(),
            features=FeatureExtractor(),
        ),
        storage=storage,  # type: ignore[arg-type]
    )
    artifact = await service.analyze_audio(asset.id)
    assert assets.asset.analysis_completed is True
    assert assets.asset.analysis_json is not None
    assert artifact.vad.speech_ratio >= 0
