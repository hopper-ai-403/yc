"""Acoustic analyzer composing detection/classification/severity."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.ai.acoustic.classifier import NoiseClassifier
from app.ai.acoustic.detector import NoiseDetector
from app.ai.acoustic.schemas import ACOUSTIC_VERSION, AcousticResult
from app.ai.acoustic.severity import NoiseSeverityEstimator
from app.audio.analysis.schemas import AnalysisArtifact
from app.shared.domain.enums import NoiseSeverity, NoiseType
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class AcousticAnalyzer:
    """Compute acoustic outputs from shared analysis artifacts."""

    def __init__(
        self,
        *,
        detector: NoiseDetector,
        classifier: NoiseClassifier,
        severity: NoiseSeverityEstimator,
    ) -> None:
        self._detector = detector
        self._classifier = classifier
        self._severity = severity

    def analyze(
        self,
        artifact: AnalysisArtifact,
        *,
        waveform: np.ndarray | None = None,
        sample_rate: int | None = None,
    ) -> AcousticResult:
        present, noise_score, noise_details = self._detector.detect(
            artifact.features,
            artifact.vad,
        )

        if present:
            bind = getattr(self._classifier, "bind_waveform", None)
            if bind is not None and waveform is not None:
                bind(waveform, sample_rate or artifact.sample_rate)
            noise_type, classification_details = self._classifier.classify(
                artifact.features,
                artifact.vad,
            )
            severity, severity_details = self._severity.estimate(
                artifact.features,
                artifact.vad,
                noise_score,
            )
        else:
            # Business rule: no noise => NONE type and NONE severity.
            noise_type = NoiseType.NONE
            severity = NoiseSeverity.NONE
            classification_details: dict[str, Any] = {}
            severity_details = {}

        result = AcousticResult(
            audio_id=artifact.audio_id,
            batch_id=artifact.batch_id,
            version=ACOUSTIC_VERSION,
            background_noise_present=present,
            background_noise_type=noise_type,
            background_noise_severity=severity,
            noise_score=noise_score,
            noise_details=noise_details,
            classification_details=classification_details,
            severity_details=severity_details,
        )
        logger.info(
            "acoustic_analysis_completed",
            audio_id=artifact.audio_id,
            background_noise_present=present,
            background_noise_type=noise_type.value,
            background_noise_severity=severity.value,
            noise_score=noise_score,
            status="ok",
        )
        return result
