"""End-to-end audio analysis pipeline (no AI classification)."""

from __future__ import annotations

import json
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path
from uuid import UUID

from app.audio.analysis.exceptions import (
    AnalysisTimeoutException,
    FeatureExtractionException,
    InvalidWaveformException,
    VADException,
)
from app.audio.analysis.features import FeatureExtractor
from app.audio.analysis.schemas import ANALYSIS_VERSION, AnalysisArtifact
from app.audio.analysis.signal import load_waveform
from app.audio.analysis.vad import VoiceActivityDetector
from app.audio.models import AudioAsset
from app.config.settings import AnalysisSettings
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)


def analysis_storage_key(batch_id: UUID, audio_id: UUID) -> str:
    return f"uploads/{batch_id}/analysis/{audio_id}.json"


class AnalysisPipeline:
    """Download normalized audio → VAD → features → upload analysis JSON."""

    def __init__(
        self,
        *,
        settings: AnalysisSettings,
        storage: StorageProvider,
        vad: VoiceActivityDetector,
        features: FeatureExtractor,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._vad = vad
        self._features = features

    async def run(self, asset: AudioAsset) -> AnalysisArtifact:
        if not asset.normalized_storage_key:
            raise InvalidWaveformException(
                "Audio must be preprocessed before analysis",
                details={"audio_id": str(asset.id)},
            )

        started = time.perf_counter()
        logger.info(
            "analysis_started",
            audio_id=str(asset.id),
            batch_id=str(asset.batch_id),
            storage_key=asset.normalized_storage_key,
        )

        download_started = time.perf_counter()
        wav_bytes = await self._storage.download(asset.normalized_storage_key)
        download_ms = int((time.perf_counter() - download_started) * 1000)

        with tempfile.TemporaryDirectory(prefix="aip-analysis-") as tmp:
            # Keep a local copy for debugging-friendly paths if needed later.
            Path(tmp, "normalized.wav").write_bytes(wav_bytes)

            def _compute() -> tuple[AnalysisArtifact, dict[str, int]]:
                waveform, sample_rate = load_waveform(
                    wav_bytes,
                    expected_sample_rate=self._settings.expected_sample_rate,
                )
                vad_started = time.perf_counter()
                vad = self._vad.detect(waveform, sample_rate)
                vad_ms = int((time.perf_counter() - vad_started) * 1000)

                feat_started = time.perf_counter()
                features = self._features.extract(
                    waveform,
                    sample_rate,
                    vad=vad,
                )
                feat_ms = int((time.perf_counter() - feat_started) * 1000)

                artifact = AnalysisArtifact(
                    audio_id=str(asset.id),
                    batch_id=str(asset.batch_id),
                    version=ANALYSIS_VERSION,
                    sample_rate=sample_rate,
                    vad=vad,
                    features=features,
                )
                return artifact, {"vad_ms": vad_ms, "features_ms": feat_ms}

            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(_compute)
                    artifact, stage_ms = future.result(
                        timeout=self._settings.timeout_seconds
                    )
            except FuturesTimeout as exc:
                raise AnalysisTimeoutException(
                    "Audio analysis timed out",
                    details={
                        "audio_id": str(asset.id),
                        "timeout": self._settings.timeout_seconds,
                    },
                ) from exc
            except (InvalidWaveformException, VADException, FeatureExtractionException):
                raise
            except Exception as exc:
                raise FeatureExtractionException(
                    "Analysis pipeline failed",
                    details={"audio_id": str(asset.id), "error": str(exc)},
                ) from exc

        upload_started = time.perf_counter()
        key = analysis_storage_key(asset.batch_id, asset.id)
        await self._storage.upload(
            key,
            json.dumps(artifact.to_storage_dict()).encode("utf-8"),
            content_type="application/json",
            metadata={
                "audio_id": str(asset.id),
                "batch_id": str(asset.batch_id),
                "stage": "analysis",
                "version": ANALYSIS_VERSION,
            },
        )
        upload_ms = int((time.perf_counter() - upload_started) * 1000)

        logger.info(
            "analysis_uploaded",
            audio_id=str(asset.id),
            storage_key=key,
            download_ms=download_ms,
            vad_ms=stage_ms.get("vad_ms"),
            features_ms=stage_ms.get("features_ms"),
            upload_ms=upload_ms,
            total_ms=int((time.perf_counter() - started) * 1000),
            status="ok",
        )
        return artifact
