"""PredictionBuilder: AnalysisResult + confidence → AssessmentPrediction."""

from __future__ import annotations

from app.prediction.schemas import (
    AnalysisResult,
    AssessmentPrediction,
    ConfidenceBreakdown,
)


class PredictionBuilder:
    """Convert aggregated analysis into the exact public assessment schema."""

    def build(
        self,
        analysis: AnalysisResult,
        confidence: ConfidenceBreakdown,
    ) -> AssessmentPrediction:
        return AssessmentPrediction(
            emotional_tone=analysis.speech.emotional_tone,
            emotional_intensity=analysis.speech.emotional_intensity,
            background_noise_present=analysis.acoustic.background_noise_present,
            background_noise_type=analysis.acoustic.background_noise_type,
            background_noise_severity=analysis.acoustic.background_noise_severity,
            audio_quality=analysis.technical.audio_quality,
            speaker_overlap_present=analysis.technical.speaker_overlap_present,
            long_silence_present=analysis.technical.long_silence_present,
            confidence=confidence.overall,
        )
