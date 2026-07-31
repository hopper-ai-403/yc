"""Acoustic analyzer composing detection/classification/severity."""

from __future__ import annotations

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

    def analyze(self, artifact: AnalysisArtifact) -> AcousticResult:
        present, noise_score, noise_details = self._detector.detect(
            artifact.features,
            artifact.vad,
        )

        if present:
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
            classification_details = {}
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
