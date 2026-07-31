"""Noise severity estimation behind a swappable interface."""

from __future__ import annotations

from typing import Protocol

from app.audio.analysis.schemas import SignalFeatures, VADResult
from app.config.settings import AcousticSettings
from app.shared.domain.enums import NoiseSeverity
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class NoiseSeverityEstimator(Protocol):
    """Interface for noise severity estimation strategies."""

    def estimate(
        self,
        features: SignalFeatures,
        vad: VADResult,
        noise_score: float,
    ) -> tuple[NoiseSeverity, dict[str, float]]:
        """Return (severity, details). Called only when noise is present."""
        ...


class DeterministicSeverityEstimator:
    """Deterministic severity from noise energy, SNR, speech ratio, noise duration."""

    def __init__(self, settings: AcousticSettings) -> None:
        self._settings = settings

    def estimate(
        self,
        features: SignalFeatures,
        vad: VADResult,
        noise_score: float,
    ) -> tuple[NoiseSeverity, dict[str, float]]:
        # Scoring (documented here per sprint rules):
        #
        #   severity_score = w_noise_ratio * noise_ratio
        #                  + w_snr         * snr_component
        #                  + w_noise_dur   * noise_duration_ratio
        #
        # noise_ratio: the detector's noise_score, a proxy for noise energy
        #              relative to the full mix.
        # snr_component: 1.0 when SNR <= severity_snr_full_at_db (noise as loud
        #              as speech), 0.0 when SNR >= severity_snr_zero_at_db,
        #              linear in between. Low SNR => noise dominates.
        # noise_duration_ratio: share of the recording that is non-speech
        #              (1 - speech_ratio). Noise that runs the whole call is
        #              more severe than a brief burst.
        #
        # Bands: score >= severity_high_threshold  -> HIGH
        #        score >= severity_medium_threshold -> MEDIUM
        #        otherwise                           -> LOW
        snr = features.snr_estimate
        if snr is None:
            snr_component = 0.5
        elif snr <= self._settings.severity_snr_full_at_db:
            snr_component = 1.0
        elif snr >= self._settings.severity_snr_zero_at_db:
            snr_component = 0.0
        else:
            span = (
                self._settings.severity_snr_zero_at_db
                - self._settings.severity_snr_full_at_db
            )
            snr_component = float(
                (self._settings.severity_snr_zero_at_db - snr) / max(span, 1e-6)
            )

        noise_duration_ratio = 1.0 - vad.speech_ratio
        severity_score = (
            self._settings.severity_noise_ratio_weight * noise_score
            + self._settings.severity_snr_weight * snr_component
            + self._settings.severity_noise_duration_weight * noise_duration_ratio
        )
        severity_score = float(min(1.0, max(0.0, severity_score)))

        if severity_score >= self._settings.severity_high_threshold:
            severity = NoiseSeverity.HIGH
        elif severity_score >= self._settings.severity_medium_threshold:
            severity = NoiseSeverity.MEDIUM
        else:
            severity = NoiseSeverity.LOW

        details = {
            "severity_score": round(severity_score, 6),
            "snr_component": round(snr_component, 6),
            "noise_ratio": round(noise_score, 6),
            "noise_duration_ratio": round(noise_duration_ratio, 6),
        }
        logger.info(
            "noise_severity_estimated",
            background_noise_severity=severity.value,
            severity_score=severity_score,
            status="ok",
        )
        return severity, details
