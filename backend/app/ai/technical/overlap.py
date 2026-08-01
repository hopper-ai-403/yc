"""Speaker overlap detection behind a swappable interface."""

from __future__ import annotations

import time
from typing import Any, Protocol

import numpy as np

from app.ai.technical.exceptions import OverlapDetectionException
from app.ai.technical.overlap_model import (
    get_or_load_overlap_pipeline,
    pyannote_dependency_available,
)
from app.audio.analysis.schemas import SignalFeatures, VADResult
from app.config.settings import TechnicalSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class OverlapDetector(Protocol):
    """Interface for speaker overlap detection strategies."""

    def detect(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[bool, float, dict[str, float]]:
        """Return (present, score, details)."""
        ...


class SignalBasedOverlapDetector:
    """Heuristic overlap detection from energy/spectral/speech density.

    Used as the default when ``TECHNICAL_OVERLAP_BACKEND=heuristic`` and as the
    automatic fallback when the pyannote backend is unavailable or fails.
    """

    def __init__(self, settings: TechnicalSettings) -> None:
        self._settings = settings

    def detect(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[bool, float, dict[str, float]]:
        try:
            density = self._speech_density(vad, features.duration)
            zcr_score = self._normalize(
                features.zero_crossing_rate,
                self._settings.overlap_zcr_min,
                self._settings.overlap_zcr_max,
            )
            bandwidth_score = self._normalize(
                features.spectral_bandwidth,
                self._settings.overlap_bandwidth_min_hz,
                self._settings.overlap_bandwidth_max_hz,
            )
            centroid_spread = self._normalize(
                features.spectral_bandwidth / max(features.spectral_centroid, 1e-6),
                self._settings.overlap_spread_min,
                self._settings.overlap_spread_max,
            )

            score = (
                self._settings.overlap_density_weight * density
                + self._settings.overlap_zcr_weight * zcr_score
                + self._settings.overlap_bandwidth_weight * bandwidth_score
                + self._settings.overlap_spread_weight * centroid_spread
            )
            score = float(min(1.0, max(0.0, score)))
            present = score >= self._settings.overlap_threshold

            details = {
                "speech_density": round(density, 6),
                "zcr_score": round(zcr_score, 6),
                "bandwidth_score": round(bandwidth_score, 6),
                "centroid_spread_score": round(centroid_spread, 6),
                "threshold": self._settings.overlap_threshold,
            }
            logger.info(
                "speaker_overlap_detected" if present else "speaker_overlap_clear",
                overlap_score=score,
                speech_density=density,
                backend="heuristic",
                selected_implementation="SignalBasedOverlapDetector",
                status="ok",
            )
            return present, round(score, 6), details
        except Exception as exc:
            raise OverlapDetectionException(
                "Failed to detect speaker overlap",
                details={"error": str(exc)},
            ) from exc

    def _speech_density(self, vad: VADResult, duration: float) -> float:
        """High segment churn per second suggests turn-taking / overlap."""
        if duration <= 0:
            return 0.0
        segments_per_second = len(vad.speech_segments) / max(duration, 1e-6)
        density = segments_per_second / self._settings.overlap_density_full_at
        return float(min(1.0, max(0.0, density)))

    @staticmethod
    def _normalize(value: float, low: float, high: float) -> float:
        if high <= low:
            return 0.0
        return float(min(1.0, max(0.0, (value - low) / (high - low))))


class PyannoteOverlapDetector:
    """Production overlap detector backed by pyannote.audio OSD.

    Satisfies ``OverlapDetector``. Accepts an optional bound normalized
    waveform via ``bind_waveform`` (same pattern as acoustic event classifiers).
    On any load/auth/inference failure, falls back to the heuristic detector
    so the technical / prediction pipeline never fails.
    """

    def __init__(
        self,
        settings: TechnicalSettings,
        *,
        heuristic: SignalBasedOverlapDetector | None = None,
        pipeline_factory: Any | None = None,
    ) -> None:
        self._settings = settings
        self._heuristic = heuristic or SignalBasedOverlapDetector(settings)
        self._pipeline_factory = pipeline_factory
        self._waveform: np.ndarray | None = None
        self._sample_rate: int | None = None

    def bind_waveform(self, waveform: np.ndarray, sample_rate: int) -> None:
        """Attach normalized mono audio for the next ``detect`` call."""
        self._waveform = np.asarray(waveform, dtype=np.float32)
        self._sample_rate = int(sample_rate)

    def detect(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[bool, float, dict[str, float]]:
        waveform = self._waveform
        sample_rate = self._sample_rate
        # Clear bind even on early fallback so state never leaks across calls.
        self._waveform = None
        self._sample_rate = None

        if waveform is None or sample_rate is None or sample_rate <= 0:
            logger.warning(
                "overlap_pyannote_waveform_missing",
                backend="pyannote",
                selected_implementation="SignalBasedOverlapDetector",
                status="fallback",
            )
            return self._heuristic.detect(features, vad)

        if not pyannote_dependency_available() and self._pipeline_factory is None:
            logger.warning(
                "overlap_pyannote_unavailable",
                reason="dependency_missing",
                backend="pyannote",
                selected_implementation="SignalBasedOverlapDetector",
                status="fallback",
            )
            return self._heuristic.detect(features, vad)

        started = time.perf_counter()
        try:
            pipeline = get_or_load_overlap_pipeline(
                self._settings,
                pipeline_factory=self._pipeline_factory,
            )
            score = self._score_overlap(
                pipeline,
                waveform=waveform,
                sample_rate=sample_rate,
                features=features,
                vad=vad,
            )
            present = score >= self._settings.overlap_threshold
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            details = {
                "threshold": self._settings.overlap_threshold,
                "overlap_ratio": round(score, 6),
                "inference_latency_ms": latency_ms,
            }
            logger.info(
                "speaker_overlap_detected" if present else "speaker_overlap_clear",
                overlap_score=round(score, 6),
                backend="pyannote",
                model_version=self._settings.overlap_model_name,
                inference_latency_ms=latency_ms,
                selected_implementation="PyannoteOverlapDetector",
                status="ok",
            )
            return present, round(score, 6), details
        except Exception as exc:
            logger.warning(
                "overlap_pyannote_inference_failed",
                error=str(exc),
                backend="pyannote",
                model_version=self._settings.overlap_model_name,
                selected_implementation="SignalBasedOverlapDetector",
                status="fallback",
            )
            return self._heuristic.detect(features, vad)

    def _score_overlap(
        self,
        pipeline: Any,
        *,
        waveform: np.ndarray,
        sample_rate: int,
        features: SignalFeatures,
        vad: VADResult,
    ) -> float:
        import torch

        mono = waveform.astype(np.float32, copy=False)
        if mono.ndim > 1:
            mono = np.mean(mono, axis=0)
        tensor = torch.from_numpy(mono).unsqueeze(0)
        output = pipeline({"waveform": tensor, "sample_rate": sample_rate})
        overlap_seconds = _annotation_duration(output)
        speech_seconds = float(vad.speech_duration or 0.0)
        if speech_seconds <= 0:
            speech_seconds = float(features.duration or 0.0)
        if speech_seconds <= 0:
            return 0.0
        return float(min(1.0, max(0.0, overlap_seconds / speech_seconds)))


def _annotation_duration(output: Any) -> float:
    """Best-effort duration of overlapped regions from a pyannote Annotation."""
    if output is None:
        return 0.0
    timeline = getattr(output, "get_timeline", None)
    if callable(timeline):
        tl = timeline()
        duration = getattr(tl, "duration", None)
        if callable(duration):
            return float(duration())
        if isinstance(duration, (int, float)):
            return float(duration)
    # Fallback: iterate segments if present.
    total = 0.0
    try:
        for segment, _, _label in output.itertracks(yield_label=True):
            total += float(getattr(segment, "duration", 0.0) or 0.0)
    except Exception:
        return 0.0
    return total
