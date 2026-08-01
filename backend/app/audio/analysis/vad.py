"""Silero-based voice activity detection."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol

import numpy as np

from app.audio.analysis.exceptions import VADException
from app.audio.analysis.schemas import TimeSegment, VADResult
from app.audio.analysis.segmentation import build_vad_result
from app.config.settings import AnalysisSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class VoiceActivityDetector(Protocol):
    """Protocol for VAD implementations."""

    def detect(self, waveform: np.ndarray, sample_rate: int) -> VADResult:
        """Detect speech activity in a mono waveform."""
        ...


@lru_cache(maxsize=1)
def _load_silero_bundle() -> tuple[Any, Any]:
    """Load Silero VAD model and utilities (cached per process)."""
    try:
        import torch
    except ImportError as exc:  # pragma: no cover
        raise VADException(
            "torch is required for Silero VAD",
            details={"error": str(exc)},
        ) from exc

    try:
        model, utils = torch.hub.load(  # type: ignore[no-untyped-call]
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
            onnx=False,
        )
    except Exception as exc:
        raise VADException(
            "Failed to load Silero VAD model",
            details={"error": str(exc)},
        ) from exc
    return model, utils


class SileroVAD:
    """Voice activity detector backed by Silero VAD."""

    def __init__(self, settings: AnalysisSettings) -> None:
        self._settings = settings

    def detect(self, waveform: np.ndarray, sample_rate: int) -> VADResult:
        if waveform.ndim != 1:
            raise VADException(
                "Silero VAD expects mono waveform",
                details={"shape": list(waveform.shape)},
            )
        if sample_rate not in {8000, 16000}:
            raise VADException(
                "Silero VAD requires 8 kHz or 16 kHz audio",
                details={"sample_rate": sample_rate},
            )

        try:
            import torch

            model, utils = _load_silero_bundle()
            get_speech_timestamps = utils[0]
            audio = torch.from_numpy(waveform.astype(np.float32, copy=False))
            timestamps = get_speech_timestamps(
                audio,
                model,
                sampling_rate=sample_rate,
                threshold=self._settings.vad_threshold,
                min_speech_duration_ms=self._settings.vad_min_speech_ms,
                min_silence_duration_ms=self._settings.vad_min_silence_ms,
                window_size_samples=self._settings.vad_window_samples,
            )
        except VADException:
            raise
        except Exception as exc:
            raise VADException(
                "Silero VAD inference failed",
                details={"error": str(exc)},
            ) from exc

        speech: list[TimeSegment] = []
        for item in timestamps or []:
            start = float(item["start"]) / float(sample_rate)
            end = float(item["end"]) / float(sample_rate)
            speech.append(TimeSegment(start=start, end=end))

        duration = float(len(waveform) / sample_rate) if sample_rate else 0.0
        result = build_vad_result(speech, total_duration=duration)
        logger.info(
            "vad_completed",
            speech_segments=len(result.speech_segments),
            speech_ratio=result.speech_ratio,
            speech_duration=result.speech_duration,
            status="ok",
        )
        return result


class EnergyVAD:
    """Lightweight energy-gate VAD used for tests / offline fallback."""

    def __init__(
        self,
        *,
        frame_ms: float = 30.0,
        hop_ms: float = 10.0,
        threshold_ratio: float = 0.1,
    ) -> None:
        self._frame_ms = frame_ms
        self._hop_ms = hop_ms
        self._threshold_ratio = threshold_ratio

    def detect(self, waveform: np.ndarray, sample_rate: int) -> VADResult:
        if sample_rate <= 0 or waveform.size == 0:
            return build_vad_result([], total_duration=0.0)

        frame = max(1, int(sample_rate * self._frame_ms / 1000.0))
        hop = max(1, int(sample_rate * self._hop_ms / 1000.0))
        energies: list[float] = []
        for start in range(0, len(waveform), hop):
            chunk = waveform[start : start + frame]
            if chunk.size == 0:
                continue
            energies.append(float(np.sqrt(np.mean(np.square(chunk)))))

        if not energies:
            duration = float(len(waveform) / sample_rate)
            return build_vad_result([], total_duration=duration)

        peak = max(energies) or 1.0
        threshold = peak * self._threshold_ratio
        speech: list[TimeSegment] = []
        in_speech = False
        seg_start = 0.0
        for index, energy in enumerate(energies):
            t0 = index * hop / sample_rate
            active = energy >= threshold
            if active and not in_speech:
                in_speech = True
                seg_start = t0
            elif not active and in_speech:
                in_speech = False
                speech.append(TimeSegment(start=seg_start, end=t0))
        if in_speech:
            speech.append(
                TimeSegment(start=seg_start, end=float(len(waveform) / sample_rate))
            )

        return build_vad_result(
            speech,
            total_duration=float(len(waveform) / sample_rate),
        )


class ResilientVAD:
    """Prefer Silero; permanently fall back to energy VAD after first failure."""

    def __init__(
        self,
        primary: VoiceActivityDetector,
        fallback: VoiceActivityDetector,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._use_fallback = False

    def detect(self, waveform: np.ndarray, sample_rate: int) -> VADResult:
        if self._use_fallback:
            return self._fallback.detect(waveform, sample_rate)
        try:
            return self._primary.detect(waveform, sample_rate)
        except Exception as exc:
            self._use_fallback = True
            logger.warning(
                "vad_primary_failed_falling_back",
                error=str(exc),
                fallback="energy",
                status="fallback",
            )
            return self._fallback.detect(waveform, sample_rate)
