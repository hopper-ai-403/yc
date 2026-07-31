"""Noise detection behind a swappable interface."""

from __future__ import annotations

from typing import Protocol

from app.ai.acoustic.exceptions import NoiseDetectionException
from app.audio.analysis.schemas import SignalFeatures, VADResult
from app.config.settings import AcousticSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class NoiseDetector(Protocol):
    """Interface for background noise detection strategies."""

    def detect(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[bool, float, dict[str, float]]:
        """Return (present, score, details)."""


class SignalBasedNoiseDetector:
    """Heuristic noise detection from SNR and silence-region spectral energy.

    Replaceable by a neural detector implementing NoiseDetector without
    changing service business logic.
    """

    def __init__(self, settings: AcousticSettings) -> None:
        self._settings = settings

    def detect(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[bool, float, dict[str, float]]:
        try:
            snr = features.snr_estimate
            # Low SNR is the strongest noise indicator. Missing SNR is neutral.
            if snr is None:
                snr_score = 0.5
            elif snr >= self._settings.severity_snr_zero_at_db:
                snr_score = 0.0
            elif snr <= self._settings.noise_snr_threshold_db:
                snr_score = 1.0
            else:
                span = (
                    self._settings.severity_snr_zero_at_db
                    - self._settings.noise_snr_threshold_db
                )
                snr_score = float(
                    (self._settings.severity_snr_zero_at_db - snr) / max(span, 1e-6)
                )

            # Energetic, broadband silence regions imply audible background noise.
            zcr_score = self._normalize(
                features.zero_crossing_rate,
                self._settings.noise_silence_zcr_min,
                self._settings.noise_silence_zcr_max,
            )
            bandwidth_score = self._normalize(
                features.spectral_bandwidth,
                self._settings.noise_bandwidth_min_hz,
                self._settings.noise_bandwidth_max_hz,
            )
            # High non-speech share with real energy implies background activity.
            non_speech_ratio = 1.0 - vad.speech_ratio

            score = (
                0.45 * snr_score
                + 0.2 * zcr_score
                + 0.15 * bandwidth_score
                + 0.2 * non_speech_ratio
            )
            score = float(min(1.0, max(0.0, score)))
            present = score >= self._settings.noise_presence_score_threshold

            details = {
                "snr_score": round(snr_score, 6),
                "zcr_score": round(zcr_score, 6),
                "bandwidth_score": round(bandwidth_score, 6),
                "non_speech_ratio": round(non_speech_ratio, 6),
                "threshold": self._settings.noise_presence_score_threshold,
            }
            logger.info(
                "background_noise_detected" if present else "background_noise_clear",
                noise_score=score,
                status="ok",
            )
            return present, round(score, 6), details
        except Exception as exc:
            raise NoiseDetectionException(
                "Failed to detect background noise",
                details={"error": str(exc)},
            ) from exc

    @staticmethod
    def _normalize(value: float, low: float, high: float) -> float:
        if high <= low:
            return 0.0
        return float(min(1.0, max(0.0, (value - low) / (high - low))))
