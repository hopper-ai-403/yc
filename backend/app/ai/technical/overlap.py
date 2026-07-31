"""Speaker overlap detection behind a swappable interface."""

from __future__ import annotations

from typing import Protocol

from app.ai.technical.exceptions import OverlapDetectionException
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

    Designed to be replaced by PyannoteOverlapDetector or NeuralOverlapDetector
    without changing service business logic.
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
    """Future pyannote-based detector (placeholder interface)."""

    def detect(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[bool, float, dict[str, float]]:
        raise OverlapDetectionException(
            "PyannoteOverlapDetector is not enabled in this sprint",
            details={"detector": "pyannote"},
        )
