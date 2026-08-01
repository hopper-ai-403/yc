"""Speech analysis pipeline: load waveform → SER inference → upload JSON."""

from __future__ import annotations

import json
import time
from uuid import UUID

from app.ai.speech.analyzer import SpeechAnalyzer
from app.ai.speech.exceptions import SpeechArtifactMissingException
from app.ai.speech.schemas import SPEECH_VERSION, SpeechResult
from app.audio.analysis.schemas import TimeSegment
from app.audio.analysis.signal import load_waveform
from app.audio.models import AudioAsset
from app.config.settings import SpeechSettings
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)


def speech_storage_key(batch_id: UUID, audio_id: UUID) -> str:
    return f"uploads/{batch_id}/speech/{audio_id}.json"


class SpeechPipeline:
    """Consume the normalized waveform and emit speech emotion results."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        analyzer: SpeechAnalyzer,
        settings: SpeechSettings,
    ) -> None:
        self._storage = storage
        self._analyzer = analyzer
        self._settings = settings

    async def run(self, asset: AudioAsset) -> SpeechResult:
        started = time.perf_counter()
        if not asset.normalized_storage_key:
            raise SpeechArtifactMissingException(
                "Normalized waveform required before speech analysis",
                details={"audio_id": str(asset.id)},
            )
        try:
            raw = await self._storage.download(asset.normalized_storage_key)
        except Exception as exc:
            raise SpeechArtifactMissingException(
                "Unable to load normalized waveform for speech analysis",
                details={
                    "audio_id": str(asset.id),
                    "key": asset.normalized_storage_key,
                    "error": str(exc),
                },
            ) from exc

        waveform, sample_rate = load_waveform(
            raw,
            expected_sample_rate=self._settings.expected_sample_rate,
        )
        speech_segments = self._load_speech_segments(asset)
        result = self._analyzer.analyze(
            audio_id=str(asset.id),
            batch_id=str(asset.batch_id),
            waveform=waveform,
            sample_rate=sample_rate,
            speech_segments=speech_segments,
        )

        key = speech_storage_key(asset.batch_id, asset.id)
        await self._storage.upload(
            key,
            json.dumps(result.to_storage_dict()).encode("utf-8"),
            content_type="application/json",
            metadata={
                "audio_id": str(asset.id),
                "batch_id": str(asset.batch_id),
                "stage": "speech",
                "version": SPEECH_VERSION,
            },
        )
        logger.info(
            "speech_uploaded",
            audio_id=str(asset.id),
            storage_key=key,
            duration_ms=int((time.perf_counter() - started) * 1000),
            status="ok",
        )
        return result

    @staticmethod
    def _load_speech_segments(asset: AudioAsset) -> list[TimeSegment] | None:
        """Best-effort VAD speech segments from the analysis artifact."""
        payload = asset.analysis_json
        if not isinstance(payload, dict):
            return None
        vad = payload.get("vad")
        if not isinstance(vad, dict):
            return None
        raw_segments = vad.get("speech_segments")
        if not isinstance(raw_segments, list) or not raw_segments:
            return None
        segments: list[TimeSegment] = []
        for item in raw_segments:
            if not isinstance(item, dict):
                continue
            try:
                segments.append(
                    TimeSegment(start=float(item["start"]), end=float(item["end"]))
                )
            except (KeyError, TypeError, ValueError):
                continue
        return segments or None
