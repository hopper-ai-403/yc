"""Confidence engine behind a swappable interface."""

from __future__ import annotations

import math
from typing import Protocol

from app.ai.technical.schemas import TechnicalResult
from app.config.settings import PredictionSettings
from app.prediction.schemas import (
    AnalysisResult,
    ConfidenceBreakdown,
)
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class ConfidenceEstimator(Protocol):
    """Interface for confidence estimation strategies."""

    def estimate(self, analysis: AnalysisResult) -> ConfidenceBreakdown:
        """Return overall confidence plus per-engine breakdown."""
        ...


class WeightedConfidenceEstimator:
    """Weighted-average confidence over engine signals.

    All weights come from PredictionSettings and are normalized at estimate time.
    Speech confidence dominates by default (60/20/20) and reflects model certainty.
    """

    def __init__(self, settings: PredictionSettings) -> None:
        self._settings = settings

    def estimate(self, analysis: AnalysisResult) -> ConfidenceBreakdown:
        speech = self._speech_confidence(analysis)
        technical = self._technical_confidence(analysis)
        acoustic = self._acoustic_confidence(analysis)

        weights = self._settings.confidence_weights
        total_weight = (
            weights.get("speech", 0.0)
            + weights.get("technical", 0.0)
            + weights.get("acoustic", 0.0)
        )
        if total_weight <= 0:
            overall = 0.0
        else:
            overall = (
                weights.get("speech", 0.0) * speech
                + weights.get("technical", 0.0) * technical
                + weights.get("acoustic", 0.0) * acoustic
            ) / total_weight

        overall = self._clamp(self._round(overall))
        breakdown = ConfidenceBreakdown(
            overall=overall,
            speech=self._clamp(self._round(speech)),
            technical=self._clamp(self._round(technical)),
            acoustic=self._clamp(self._round(acoustic)),
        )
        logger.info(
            "ConfidenceCalculated",
            overall=breakdown.overall,
            speech=breakdown.speech,
            technical=breakdown.technical,
            acoustic=breakdown.acoustic,
            status="ok",
        )
        return breakdown

    def _speech_confidence(self, analysis: AnalysisResult) -> float:
        """SER certainty from top probability, margin, and entropy when available."""
        speech = analysis.speech
        probs = [max(0.0, float(v)) for v in speech.tone_probabilities.values()]
        if len(probs) >= 2:
            return self._certainty_from_distribution(probs)
        return float(speech.top_probability)

    def _certainty_from_distribution(self, probs: list[float]) -> float:
        total = sum(probs)
        if total <= 0:
            return 0.0
        normalized = [p / total for p in probs]
        ordered = sorted(normalized, reverse=True)
        top1 = ordered[0]
        top2 = ordered[1] if len(ordered) > 1 else 0.0
        margin = max(0.0, top1 - top2)
        if len(normalized) == 1:
            entropy_norm = 0.0
        else:
            entropy = -sum(p * math.log(p + 1e-12) for p in normalized)
            entropy_norm = entropy / math.log(len(normalized))
        inverse_entropy = 1.0 - entropy_norm

        w_top = self._settings.confidence_speech_top_weight
        w_margin = self._settings.confidence_speech_margin_weight
        w_entropy = self._settings.confidence_speech_entropy_weight
        weight_sum = w_top + w_margin + w_entropy
        if weight_sum <= 0:
            return top1
        certainty = (
            w_top * top1 + w_margin * margin + w_entropy * inverse_entropy
        ) / weight_sum
        return float(min(1.0, max(0.0, certainty)))

    def _technical_confidence(self, analysis: AnalysisResult) -> float:
        """Weighted quality / overlap / silence components."""
        technical = analysis.technical
        sub = self._settings.confidence_technical_weights
        quality = technical.quality_score / 100.0
        overlap = 1.0 - technical.overlap_score
        silence = self._silence_score(technical)
        total = (
            sub.get("quality", 0.0) + sub.get("overlap", 0.0) + sub.get("silence", 0.0)
        )
        if total <= 0:
            return 0.0
        return (
            sub.get("quality", 0.0) * quality
            + sub.get("overlap", 0.0) * overlap
            + sub.get("silence", 0.0) * silence
        ) / total

    def _acoustic_confidence(self, analysis: AnalysisResult) -> float:
        """Distance of the noise score from the decision boundary."""
        acoustic = analysis.acoustic
        if acoustic.background_noise_present:
            return float(acoustic.noise_score)
        return 1.0 - float(acoustic.noise_score)

    @staticmethod
    def _silence_score(technical: TechnicalResult) -> float:
        """1.0 far below the long-silence threshold, 0.0 once flagged."""
        details = technical.silence_details
        largest = float(details.get("largest_silence_seconds", 0.0))
        threshold = float(details.get("threshold_largest_silence_seconds", 0.0))
        if technical.long_silence_present or threshold <= 0:
            return 0.0 if technical.long_silence_present else 1.0
        return max(0.0, 1.0 - largest / threshold)

    def _round(self, value: float) -> float:
        return round(value, self._settings.confidence_rounding)

    @staticmethod
    def _clamp(value: float) -> float:
        return float(min(1.0, max(0.0, value)))
