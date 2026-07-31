"""Long silence detection using VAD artifacts."""

from __future__ import annotations

from app.audio.analysis.schemas import VADResult
from app.config.settings import TechnicalSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class LongSilenceDetector:
    """Deterministic long-silence rules over VAD output."""

    def __init__(self, settings: TechnicalSettings) -> None:
        self._settings = settings

    def detect(self, vad: VADResult) -> tuple[bool, dict[str, float]]:
        """Return (present, details) for long silence."""
        silence_duration = sum(s.duration for s in vad.silence_segments)
        total_duration = vad.speech_duration + silence_duration
        silence_ratio = (
            (silence_duration / total_duration) if total_duration > 0 else 0.0
        )

        present = (
            vad.largest_silence >= self._settings.long_silence_seconds
            or silence_ratio >= self._settings.total_silence_ratio
            or vad.speech_ratio <= self._settings.min_speech_ratio
        )

        details = {
            "largest_silence_seconds": vad.largest_silence,
            "threshold_largest_silence_seconds": self._settings.long_silence_seconds,
            "total_silence_ratio": round(silence_ratio, 6),
            "threshold_total_silence_ratio": self._settings.total_silence_ratio,
            "speech_ratio": vad.speech_ratio,
            "threshold_min_speech_ratio": self._settings.min_speech_ratio,
        }

        logger.info(
            "long_silence_detected" if present else "long_silence_clear",
            largest_silence=vad.largest_silence,
            silence_ratio=silence_ratio,
            speech_ratio=vad.speech_ratio,
            status="ok",
        )
        return present, details
