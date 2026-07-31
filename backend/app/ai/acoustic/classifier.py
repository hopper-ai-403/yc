"""Noise classification behind a swappable interface."""

from __future__ import annotations

from typing import Protocol

from app.ai.acoustic.exceptions import NoiseClassificationException
from app.audio.analysis.schemas import SignalFeatures, VADResult
from app.config.settings import AcousticSettings
from app.shared.domain.enums import NoiseType
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class NoiseClassifier(Protocol):
    """Interface for noise type classification strategies."""

    def classify(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[NoiseType, dict[str, float]]:
        """Return (noise_type, details). Called only when noise is present."""
        ...


class HeuristicNoiseClassifier:
    """Rule-based classifier over spectral/temporal signatures.

    Replaceable by a neural classifier implementing NoiseClassifier without
    changing service business logic.
    """

    def __init__(self, settings: AcousticSettings) -> None:
        self._settings = settings

    def classify(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[NoiseType, dict[str, float]]:
        try:
            centroid = features.spectral_centroid
            bandwidth = features.spectral_bandwidth
            rolloff = features.spectral_rolloff
            zcr = features.zero_crossing_rate
            segments = len(vad.speech_segments)

            # Ordered rules; first match wins. Anchors are settings-driven.
            if (
                centroid >= self._settings.classify_music_centroid_hz
                and rolloff >= self._settings.classify_music_rolloff_hz
            ):
                noise_type = NoiseType.MUSIC
            elif zcr >= self._settings.classify_static_zcr:
                noise_type = NoiseType.STATIC
            elif zcr >= self._settings.classify_keyboard_zcr and segments >= 4:
                noise_type = NoiseType.KEYBOARD
            elif (
                bandwidth >= self._settings.classify_wind_bandwidth_hz
                and centroid <= self._settings.classify_wind_centroid_hz
            ):
                noise_type = NoiseType.WIND
            elif centroid <= self._settings.classify_traffic_centroid_hz:
                noise_type = NoiseType.TRAFFIC
            elif segments >= self._settings.classify_chatter_min_segments:
                noise_type = NoiseType.OFFICE_CHATTER
            else:
                noise_type = NoiseType.OTHER

            details = {
                "spectral_centroid": round(centroid, 3),
                "spectral_bandwidth": round(bandwidth, 3),
                "spectral_rolloff": round(rolloff, 3),
                "zero_crossing_rate": round(zcr, 6),
                "speech_segment_count": float(segments),
            }
            logger.info(
                "noise_classified",
                background_noise_type=noise_type.value,
                status="ok",
            )
            return noise_type, details
        except Exception as exc:
            raise NoiseClassificationException(
                "Failed to classify background noise",
                details={"error": str(exc)},
            ) from exc


class NeuralNoiseClassifier:
    """Future neural classifier (placeholder interface)."""

    def classify(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[NoiseType, dict[str, float]]:
        raise NoiseClassificationException(
            "NeuralNoiseClassifier is not enabled in this sprint",
            details={"classifier": "neural"},
        )
