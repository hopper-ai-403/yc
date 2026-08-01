"""Unit tests for preprocessing pipeline and service (mocked ffmpeg/R2)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

import app.shared.database.models_registry  # noqa: F401
from app.audio.models import AudioAsset
from app.audio.preprocessing.exceptions import InvalidMetadataException
from app.audio.preprocessing.ffmpeg import build_edge_silence_trim_filter
from app.audio.preprocessing.metadata import (
    AudioTechnicalMetadata,
    ProbeFormat,
    ProbeResult,
    ProbeStream,
)
from app.audio.preprocessing.pipeline import (
    PreprocessingPipeline,
    metadata_storage_key,
    normalized_storage_key,
)
from app.audio.preprocessing.policy import (
    PREPROCESSING_POLICY_VERSION,
    is_preprocessing_stale,
)
from app.audio.preprocessing.service import PreprocessingService
from app.audio.preprocessing.validator import AudioValidator
from app.config.settings import PreprocessingSettings
from app.shared.domain.enums import AudioStatus


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        del content_type, metadata
        payload = data if isinstance(data, bytes) else bytes(data)
        self.objects[key] = payload
        return key

    async def download(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def list(self, prefix: str = "", *, max_keys: int = 1000) -> list[str]:
        return [k for k in self.objects if k.startswith(prefix)][:max_keys]

    async def generate_signed_url(
        self,
        key: str,
        *,
        expires_in: int = 3600,
        method: str = "GET",
    ) -> str:
        return f"https://example.test/{key}?e={expires_in}&m={method}"

    async def health_check(self) -> bool:
        return True


class FakeProbe:
    def __init__(
        self,
        *,
        sample_rate: str = "44100",
        channels: int = 2,
        codec: str = "pcm_s16le",
        original_duration: str = "45.0",
        normalized_duration: str = "45.0",
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.codec = codec
        self.original_duration = original_duration
        self.normalized_duration = normalized_duration
        self.calls = 0

    def probe(self, path: Path) -> ProbeResult:
        self.calls += 1
        # After normalize, report target format.
        if path.name.startswith("normalized"):
            return ProbeResult(
                streams=[
                    ProbeStream(
                        codec_type="audio",
                        codec_name="pcm_s16le",
                        sample_rate="16000",
                        channels=1,
                        duration=self.normalized_duration,
                    )
                ],
                format=ProbeFormat(
                    format_name="wav",
                    duration=self.normalized_duration,
                    size="6400",
                ),
            )
        return ProbeResult(
            streams=[
                ProbeStream(
                    codec_type="audio",
                    codec_name=self.codec,
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    duration=self.original_duration,
                    bit_rate="1411200",
                )
            ],
            format=ProbeFormat(
                format_name="wav",
                duration=self.original_duration,
                size="17640",
            ),
        )


class FakeFFmpeg:
    def measure_levels(self, path: Path) -> tuple[float | None, float | None]:
        del path
        return -1.5, -18.0

    def normalize(self, input_path: Path, output_path: Path) -> None:
        # Simulate conversion by writing a non-empty wav header-ish payload.
        del input_path
        output_path.write_bytes(b"RIFF" + b"\x00" * 44)


class FakeNormalizer:
    target_sample_rate = 16000
    target_channels = 1
    target_codec = "pcm_s16le"

    def __init__(self, ffmpeg: FakeFFmpeg) -> None:
        self._ffmpeg = ffmpeg

    def normalize(self, input_path: Path, output_path: Path) -> Path:
        self._ffmpeg.normalize(input_path, output_path)
        return output_path


class FakeAssets:
    def __init__(self, asset: AudioAsset) -> None:
        self.asset = asset
        self.invalidate_calls = 0

    async def create(self, asset: AudioAsset) -> AudioAsset:
        self.asset = asset
        return asset

    async def find_by_id(self, asset_id: Any) -> AudioAsset | None:
        return self.asset if self.asset.id == asset_id else None

    async def find_by_batch(self, batch_id: Any) -> list[AudioAsset]:
        return [self.asset] if self.asset.batch_id == batch_id else []

    async def update_status(self, asset_id: Any, status: AudioStatus) -> AudioAsset:
        self.asset.processing_status = status
        return self.asset

    async def save_preprocessing_result(
        self, asset_id: Any, **kwargs: Any
    ) -> AudioAsset:
        self.asset.duration = kwargs["duration"]
        self.asset.sample_rate = kwargs["sample_rate"]
        self.asset.channels = kwargs["channels"]
        self.asset.normalized_storage_key = kwargs["normalized_storage_key"]
        self.asset.metadata_json = dict(kwargs["metadata_json"])
        self.asset.metadata_json["metadata_storage_key"] = kwargs[
            "metadata_storage_key"
        ]
        self.asset.is_preprocessed = True
        self.asset.preprocessed_at = kwargs["preprocessed_at"]
        return self.asset

    async def invalidate_downstream_artifacts(self, asset_id: Any) -> AudioAsset:
        del asset_id
        self.invalidate_calls += 1
        self.asset.is_preprocessed = False
        self.asset.analysis_completed = False
        self.asset.analysis_json = None
        self.asset.technical_completed = False
        self.asset.technical_json = None
        self.asset.acoustic_completed = False
        self.asset.acoustic_json = None
        self.asset.speech_completed = False
        self.asset.speech_json = None
        self.asset.prediction = None
        return self.asset


def _asset(*, sample_ext: str = "wav") -> AudioAsset:
    batch_id = uuid4()
    asset = AudioAsset(
        batch_id=batch_id,
        filename=f"call.{sample_ext}",
        format=sample_ext,
        extension=sample_ext,
        mime_type=f"audio/{sample_ext}",
        size_bytes=17640,
        checksum_sha256="a" * 64,
        uploaded_at=datetime.now(timezone.utc),
        storage_key=f"uploads/{batch_id}/original/call.{sample_ext}",
        processing_status=AudioStatus.PROCESSING,
        is_preprocessed=False,
    )
    asset.id = uuid4()
    return asset


def _pipeline(
    storage: FakeStorage,
    *,
    sample_rate: str = "44100",
    channels: int = 2,
    codec: str = "pcm_s16le",
    original_duration: str = "45.0",
    normalized_duration: str = "45.0",
    settings: PreprocessingSettings | None = None,
) -> PreprocessingPipeline:
    preprocess_settings = settings or PreprocessingSettings()
    ffmpeg = FakeFFmpeg()
    return PreprocessingPipeline(
        settings=preprocess_settings,
        storage=storage,  # type: ignore[arg-type]
        ffprobe=FakeProbe(  # type: ignore[arg-type]
            sample_rate=sample_rate,
            channels=channels,
            codec=codec,
            original_duration=original_duration,
            normalized_duration=normalized_duration,
        ),
        ffmpeg=ffmpeg,  # type: ignore[arg-type]
        validator=AudioValidator(preprocess_settings),
        normalizer=FakeNormalizer(ffmpeg),  # type: ignore[arg-type]
    )


def test_edge_trim_filter_never_uses_stop_periods() -> None:
    filt = build_edge_silence_trim_filter(
        silence_min_duration_seconds=0.1,
        silence_threshold_db=-50.0,
    )
    assert "stop_periods" not in filt
    assert "areverse" in filt
    assert filt.count("silenceremove=") == 2


def test_policy_marks_collapsed_and_legacy_metadata_stale() -> None:
    settings = PreprocessingSettings(trim_silence=False)
    collapsed = {
        "duration": 45.0,
        "normalized_duration": 0.1,
        "preprocessing_policy_version": PREPROCESSING_POLICY_VERSION,
        "trim_silence": False,
        "trim_mode": "none",
    }
    assert is_preprocessing_stale(collapsed, settings) is True

    legacy = {
        "duration": 45.0,
        "normalized_duration": 45.0,
    }
    assert is_preprocessing_stale(legacy, settings) is True

    current = {
        "duration": 45.0,
        "normalized_duration": 44.8,
        "preprocessing_policy_version": PREPROCESSING_POLICY_VERSION,
        "trim_silence": False,
        "trim_mode": "none",
    }
    assert is_preprocessing_stale(current, settings) is False


@pytest.mark.asyncio
async def test_pipeline_stereo_44k_to_mono_16k_and_r2_upload() -> None:
    storage = FakeStorage()
    asset = _asset()
    storage.objects[asset.storage_key] = b"RIFF" + b"\x00" * 64

    pipeline = _pipeline(storage, sample_rate="44100", channels=2)
    metadata = await pipeline.run(asset)

    assert metadata.sample_rate == 44100
    assert metadata.channels == 2
    assert metadata.normalized_sample_rate == 16000
    assert metadata.normalized_channels == 1
    assert metadata.normalized_codec == "pcm_s16le"
    assert metadata.preprocessing_policy_version == PREPROCESSING_POLICY_VERSION
    assert metadata.trim_mode == "none"

    wav_key = normalized_storage_key(asset.batch_id, asset.id)
    meta_key = metadata_storage_key(asset.batch_id, asset.id)
    assert wav_key in storage.objects
    assert meta_key in storage.objects
    assert storage.objects[wav_key].startswith(b"RIFF")


@pytest.mark.asyncio
async def test_pipeline_rejects_collapsed_normalized_duration() -> None:
    storage = FakeStorage()
    asset = _asset()
    storage.objects[asset.storage_key] = b"RIFF" + b"\x00" * 64
    pipeline = _pipeline(
        storage,
        original_duration="45.0",
        normalized_duration="0.1",
    )
    with pytest.raises(InvalidMetadataException, match="collapsed"):
        await pipeline.run(asset)


@pytest.mark.asyncio
async def test_pipeline_8k_and_mp3_ogg_codecs() -> None:
    for codec, ext, rate in (
        ("mp3", "mp3", "44100"),
        ("vorbis", "ogg", "48000"),
        ("pcm_s16le", "wav", "8000"),
    ):
        storage = FakeStorage()
        asset = _asset(sample_ext=ext)
        storage.objects[asset.storage_key] = b"OggS" + b"\x00" * 64
        pipeline = _pipeline(storage, sample_rate=rate, channels=1, codec=codec)
        metadata = await pipeline.run(asset)
        assert metadata.codec == codec
        assert metadata.normalized_sample_rate == 16000


@pytest.mark.asyncio
async def test_service_idempotency_skips_completed() -> None:
    asset = _asset()
    asset.is_preprocessed = True
    asset.normalized_storage_key = normalized_storage_key(asset.batch_id, asset.id)
    asset.metadata_json = AudioTechnicalMetadata(
        duration=45.0,
        sample_rate=16000,
        channels=1,
        codec="pcm_s16le",
        container="wav",
        file_size=100,
        normalized_sample_rate=16000,
        normalized_channels=1,
        normalized_codec="pcm_s16le",
        normalized_duration=45.0,
        preprocessing_policy_version=PREPROCESSING_POLICY_VERSION,
        trim_silence=False,
        trim_mode="none",
    ).to_storage_dict()

    class BoomPipeline:
        async def run(self, _asset: AudioAsset) -> AudioTechnicalMetadata:
            raise AssertionError("pipeline should not run")

    service = PreprocessingService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        pipeline=BoomPipeline(),  # type: ignore[arg-type]
        settings=PreprocessingSettings(trim_silence=False),
    )
    result = await service.preprocess_audio(asset.id)
    assert result.normalized_sample_rate == 16000


@pytest.mark.asyncio
async def test_service_reprocesses_stale_and_invalidates_downstream() -> None:
    asset = _asset()
    asset.is_preprocessed = True
    asset.analysis_completed = True
    asset.analysis_json = {"vad": True}
    asset.normalized_storage_key = normalized_storage_key(asset.batch_id, asset.id)
    # Legacy / collapsed artifact from mid-call silence trim.
    asset.metadata_json = {
        "duration": 45.0,
        "normalized_duration": 0.1,
        "sample_rate": 44100,
        "channels": 1,
        "codec": "pcm_s16le",
        "container": "wav",
        "file_size": 100,
        "normalized_sample_rate": 16000,
        "normalized_channels": 1,
        "normalized_codec": "pcm_s16le",
    }

    storage = FakeStorage()
    storage.objects[asset.storage_key] = b"RIFF" + b"\x00" * 64
    assets = FakeAssets(asset)
    service = PreprocessingService(
        assets=assets,  # type: ignore[arg-type]
        pipeline=_pipeline(storage),
        settings=PreprocessingSettings(trim_silence=False),
    )
    meta = await service.preprocess_audio(asset.id)
    assert assets.invalidate_calls == 1
    assert assets.asset.is_preprocessed is True
    assert assets.asset.analysis_completed is False
    assert meta.normalized_duration == 45.0
    assert meta.preprocessing_policy_version == PREPROCESSING_POLICY_VERSION


@pytest.mark.asyncio
async def test_service_persists_metadata() -> None:
    storage = FakeStorage()
    asset = _asset()
    storage.objects[asset.storage_key] = b"RIFF" + b"\x00" * 64
    assets = FakeAssets(asset)
    service = PreprocessingService(
        assets=assets,  # type: ignore[arg-type]
        pipeline=_pipeline(storage),
        settings=PreprocessingSettings(),
    )
    meta = await service.preprocess_audio(asset.id)
    assert assets.asset.is_preprocessed is True
    assert assets.asset.normalized_storage_key is not None
    assert assets.asset.metadata_json is not None
    assert meta.duration == 45.0
    assert meta.normalized_duration == 45.0
