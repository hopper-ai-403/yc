"""Deterministic audio quality scoring (no AI model)."""

from __future__ import annotations

from app.ai.technical.exceptions import QualityScoringException
from app.ai.technical.schemas import QualityBreakdown
from app.audio.analysis.schemas import SignalFeatures, VADResult
from app.config.settings import TechnicalSettings
from app.shared.domain.enums import AudioQuality
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)

_CLIP_THRESHOLD = 0.99


class AudioQualityAnalyzer:
    """Score quality from Sprint 5 signal features."""

    def __init__(self, settings: TechnicalSettings) -> None:
        self._settings = settings

    def score(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[AudioQuality, QualityBreakdown, float]:
        try:
            snr_penalty = self._snr_penalty(features.snr_estimate)
            clipping_penalty = self._clipping_penalty(features)
            dynamic_range_penalty = self._dynamic_range_penalty(features.dynamic_range)
            silence_penalty = self._silence_penalty(vad)
            speech_presence_penalty = self._speech_presence_penalty(vad.speech_ratio)

            total = (
                snr_penalty
                + clipping_penalty
                + dynamic_range_penalty
                + silence_penalty
                + speech_presence_penalty
            )
            total = float(min(100.0, max(0.0, total)))
            quality_score = round(100.0 - total, 4)

            if quality_score >= self._settings.clear_threshold:
                quality = AudioQuality.CLEAR
            elif quality_score >= self._settings.slightly_impaired_threshold:
                quality = AudioQuality.SLIGHTLY_IMPAIRED
            else:
                quality = AudioQuality.SEVERELY_IMPAIRED

            breakdown = QualityBreakdown(
                snr_penalty=snr_penalty,
                clipping_penalty=clipping_penalty,
                dynamic_range_penalty=dynamic_range_penalty,
                silence_penalty=silence_penalty,
                speech_presence_penalty=speech_presence_penalty,
                total_penalty=total,
            )
            logger.info(
                "quality_scored",
                audio_quality=quality.value,
                quality_score=quality_score,
                total_penalty=total,
                status="ok",
            )
            return quality, breakdown, quality_score
        except Exception as exc:
            raise QualityScoringException(
                "Failed to score audio quality",
                details={"error": str(exc)},
            ) from exc

    def _snr_penalty(self, snr_estimate: float | None) -> float:
        if snr_estimate is None:
            return self._settings.missing_snr_penalty
        if snr_estimate >= self._settings.snr_good_db:
            return 0.0
        if snr_estimate >= self._settings.snr_ok_db:
            span = self._settings.snr_good_db - self._settings.snr_ok_db
            return float(
                (self._settings.snr_good_db - snr_estimate)
                / max(span, 1e-6)
                * self._settings.snr_penalty_weight
            )
        return self._settings.snr_penalty_weight

    def _clipping_penalty(self, features: SignalFeatures) -> float:
        if features.peak_amplitude < _CLIP_THRESHOLD:
            return 0.0
        # Estimation: very hot peaks combined with compressed dynamics.
        compression = max(0.0, self._settings.dynamic_range_good_db - features.dynamic_range)
        ratio = min(1.0, compression / max(self._settings.dynamic_range_good_db, 1e-6))
        return float(self._settings.clipping_penalty_weight * ratio)

    def _dynamic_range_penalty(self, dynamic_range_db: float) -> float:
        if dynamic_range_db >= self._settings.dynamic_range_good_db:
            return 0.0
        if dynamic_range_db <= self._settings.dynamic_range_bad_db:
            return self._settings.dynamic_range_penalty_weight
        span = self._settings.dynamic_range_good_db - self._settings.dynamic_range_bad_db
        return float(
            (self._settings.dynamic_range_good_db - dynamic_range_db)
            / max(span, 1e-6)
            * self._settings.dynamic_range_penalty_weight
        )

    def _silence_penalty(self, vad: VADResult) -> float:
        silence_ratio = 1.0 - vad.speech_ratio
        if silence_ratio <= self._settings.silence_ratio_warn:
            return 0.0
        if silence_ratio >= self._settings.silence_ratio_bad:
            return self._settings.silence_penalty_weight
        span = self._settings.silence_ratio_bad - self._settings.silence_ratio_warn
        return float(
            (silence_ratio - self._settings.silence_ratio_warn)
            / max(span, 1e-6)
            * self._settings.silence_penalty_weight
        )

    def _speech_presence_penalty(self, speech_ratio: float) -> float:
        if speech_ratio >= self._settings.speech_ratio_good:
            return 0.0
        if speech_ratio <= self._settings.speech_ratio_bad:
            return self._settings.speech_presence_penalty_weight
        span = self._settings.speech_ratio_good - self._settings.speech_ratio_bad
        return float(
            (self._settings.speech_ratio_good - speech_ratio)
            / max(span, 1e-6)
            * self._settings.speech_presence_penalty_weight
        )
