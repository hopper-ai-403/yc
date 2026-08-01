"""End-to-end audio preprocessing pipeline (no AI)."""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path
from uuid import UUID

from app.audio.models import AudioAsset
from app.audio.preprocessing.exceptions import (
    AudioDownloadException,
    AudioUploadException,
    InvalidMetadataException,
)
from app.audio.preprocessing.ffmpeg import FFmpegClient
from app.audio.preprocessing.ffprobe import FFprobeClient
from app.audio.preprocessing.metadata import AudioTechnicalMetadata, ProbeResult
from app.audio.preprocessing.normalizer import AudioNormalizer
from app.audio.preprocessing.policy import (
    duration_delta_ratio,
    is_duration_collapsed,
    is_duration_out_of_tolerance,
    preprocessing_fingerprint,
)
from app.audio.preprocessing.validator import AudioValidator
from app.config.settings import PreprocessingSettings
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)


def normalized_storage_key(batch_id: UUID, audio_id: UUID) -> str:
    return f"uploads/{batch_id}/normalized/{audio_id}.wav"


def metadata_storage_key(batch_id: UUID, audio_id: UUID) -> str:
    return f"uploads/{batch_id}/metadata/{audio_id}.json"


class PreprocessingPipeline:
    """Download → validate → probe → normalize → upload → build metadata."""

    def __init__(
        self,
        *,
        settings: PreprocessingSettings,
        storage: StorageProvider,
        ffprobe: FFprobeClient,
        ffmpeg: FFmpegClient,
        validator: AudioValidator,
        normalizer: AudioNormalizer,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._ffprobe = ffprobe
        self._ffmpeg = ffmpeg
        self._validator = validator
        self._normalizer = normalizer

    async def run(self, asset: AudioAsset) -> AudioTechnicalMetadata:
        """Execute the full preprocessing pipeline for one asset."""
        suffix = Path(asset.filename).suffix or f".{asset.extension or 'bin'}"
        with tempfile.TemporaryDirectory(prefix="aip-preprocess-") as tmp:
            tmp_dir = Path(tmp)
            original_path = tmp_dir / f"original{suffix}"
            normalized_path = tmp_dir / "normalized.wav"

            download_ms = await self._download(asset, original_path)
            self._validator.validate_file_bytes(
                original_path.read_bytes(),
                filename=asset.filename,
            )

            probe_started = time.perf_counter()
            probe = self._ffprobe.probe(original_path)
            self._validator.validate_probe(probe, path=original_path)
            probe_ms = int((time.perf_counter() - probe_started) * 1000)

            levels_started = time.perf_counter()
            peak_db, rms_db = self._ffmpeg.measure_levels(original_path)
            levels_ms = int((time.perf_counter() - levels_started) * 1000)

            normalize_started = time.perf_counter()
            self._normalizer.normalize(original_path, normalized_path)
            normalize_ms = int((time.perf_counter() - normalize_started) * 1000)

            normalized_probe = self._ffprobe.probe(normalized_path)
            metadata = self._build_metadata(
                asset=asset,
                original_probe=probe,
                normalized_probe=normalized_probe,
                original_size=original_path.stat().st_size,
                normalized_size=normalized_path.stat().st_size,
                peak_db=peak_db,
                rms_db=rms_db,
            )
            self._assert_duration_integrity(metadata, audio_id=asset.id)

            upload_ms = await self._upload(
                asset,
                normalized_path,
                metadata,
            )

            logger.info(
                "preprocessing_pipeline_complete",
                audio_id=str(asset.id),
                batch_id=str(asset.batch_id),
                download_ms=download_ms,
                probe_ms=probe_ms,
                levels_ms=levels_ms,
                normalize_ms=normalize_ms,
                upload_ms=upload_ms,
                status="ok",
            )
            return metadata

    async def _download(self, asset: AudioAsset, destination: Path) -> int:
        started = time.perf_counter()
        logger.info(
            "download_started",
            audio_id=str(asset.id),
            storage_key=asset.storage_key,
        )
        try:
            data = await self._storage.download(asset.storage_key)
        except Exception as exc:
            raise AudioDownloadException(
                "Failed to download original audio from R2",
                details={
                    "audio_id": str(asset.id),
                    "storage_key": asset.storage_key,
                    "error": str(exc),
                },
            ) from exc
        await asyncio.to_thread(destination.write_bytes, data)
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "download_complete",
            audio_id=str(asset.id),
            size_bytes=len(data),
            duration_ms=duration_ms,
            status="ok",
        )
        return duration_ms

    async def _upload(
        self,
        asset: AudioAsset,
        normalized_path: Path,
        metadata: AudioTechnicalMetadata,
    ) -> int:
        started = time.perf_counter()
        wav_key = normalized_storage_key(asset.batch_id, asset.id)
        meta_key = metadata_storage_key(asset.batch_id, asset.id)
        try:
            normalized_bytes = await asyncio.to_thread(normalized_path.read_bytes)
            await self._storage.upload(
                wav_key,
                normalized_bytes,
                content_type="audio/wav",
                metadata={
                    "audio_id": str(asset.id),
                    "batch_id": str(asset.batch_id),
                    "stage": "normalized",
                },
            )
            await self._storage.upload(
                meta_key,
                json.dumps(metadata.to_storage_dict()).encode("utf-8"),
                content_type="application/json",
                metadata={
                    "audio_id": str(asset.id),
                    "batch_id": str(asset.batch_id),
                    "stage": "metadata",
                },
            )
        except Exception as exc:
            raise AudioUploadException(
                "Failed to upload normalized audio or metadata",
                details={
                    "audio_id": str(asset.id),
                    "normalized_key": wav_key,
                    "metadata_key": meta_key,
                    "error": str(exc),
                },
            ) from exc

        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "upload_complete",
            audio_id=str(asset.id),
            normalized_key=wav_key,
            metadata_key=meta_key,
            duration_ms=duration_ms,
            status="ok",
        )
        return duration_ms

    def _build_metadata(
        self,
        *,
        asset: AudioAsset,
        original_probe: ProbeResult,
        normalized_probe: ProbeResult,
        original_size: int,
        normalized_size: int,
        peak_db: float | None,
        rms_db: float | None,
    ) -> AudioTechnicalMetadata:
        original_stream = self._first_audio_stream(original_probe)
        normalized_stream = self._first_audio_stream(normalized_probe)
        if original_stream is None or normalized_stream is None:
            raise InvalidMetadataException(
                "Could not locate audio stream in probe result",
                details={"audio_id": str(asset.id)},
            )

        duration = self._float(original_stream.duration)
        if duration is None and original_probe.format is not None:
            duration = self._float(original_probe.format.duration)
        sample_rate = self._int(original_stream.sample_rate)
        channels = original_stream.channels
        bitrate = self._int(original_stream.bit_rate)
        if bitrate is None and original_probe.format is not None:
            bitrate = self._int(original_probe.format.bit_rate)

        container = (
            (original_probe.format.format_name if original_probe.format else None)
            or asset.format
            or "unknown"
        )
        codec = original_stream.codec_name or "unknown"

        if duration is None or sample_rate is None or channels is None:
            raise InvalidMetadataException(
                "Incomplete original metadata",
                details={
                    "duration": duration,
                    "sample_rate": sample_rate,
                    "channels": channels,
                },
            )

        normalized_duration = self._float(normalized_stream.duration)
        if normalized_duration is None and normalized_probe.format is not None:
            normalized_duration = self._float(normalized_probe.format.duration)

        fingerprint = preprocessing_fingerprint(self._settings)
        return AudioTechnicalMetadata(
            duration=duration,
            sample_rate=sample_rate,
            channels=channels,
            bitrate=bitrate,
            codec=codec,
            container=container.split(",")[0],
            file_size=original_size,
            peak_db=peak_db,
            rms_db=rms_db,
            normalized_sample_rate=self._normalizer.target_sample_rate,
            normalized_channels=self._normalizer.target_channels,
            normalized_codec=self._normalizer.target_codec,
            normalized_file_size=normalized_size,
            normalized_duration=normalized_duration,
            preprocessing_policy_version=fingerprint["preprocessing_policy_version"],
            trim_silence=fingerprint["trim_silence"],
            trim_mode=fingerprint["trim_mode"],
        )

    def _assert_duration_integrity(
        self,
        metadata: AudioTechnicalMetadata,
        *,
        audio_id: UUID,
    ) -> None:
        """Reject collapsed or out-of-tolerance normalized audio."""
        original = metadata.duration
        normalized = metadata.normalized_duration
        if is_duration_collapsed(original, normalized):
            raise InvalidMetadataException(
                "Normalized audio duration collapsed; conversational audio must "
                "not be reduced to a sub-second clip",
                details={
                    "audio_id": str(audio_id),
                    "original_duration": original,
                    "normalized_duration": normalized,
                },
            )

        if self._settings.trim_silence:
            return

        if is_duration_out_of_tolerance(
            original,
            normalized,
            max_delta_ratio=self._settings.max_duration_delta_ratio,
        ):
            ratio = (
                duration_delta_ratio(original, normalized)
                if normalized is not None
                else None
            )
            raise InvalidMetadataException(
                "Normalized duration differs from original by more than "
                f"{self._settings.max_duration_delta_ratio:.0%}",
                details={
                    "audio_id": str(audio_id),
                    "original_duration": original,
                    "normalized_duration": normalized,
                    "delta_ratio": ratio,
                    "max_delta_ratio": self._settings.max_duration_delta_ratio,
                },
            )

    @staticmethod
    def _first_audio_stream(probe: ProbeResult):
        for stream in probe.streams:
            if (stream.codec_type or "").lower() == "audio":
                return stream
        return None

    @staticmethod
    def _float(value: str | float | int | None) -> float | None:
        if value is None or value == "N/A":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _int(value: str | float | int | None) -> int | None:
        if value is None or value == "N/A":
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
