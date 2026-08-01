"""Technical analyzer composing silence/quality/overlap."""

from __future__ import annotations

import numpy as np

from app.ai.technical.overlap import OverlapDetector
from app.ai.technical.quality import AudioQualityAnalyzer
from app.ai.technical.schemas import TECHNICAL_VERSION, TechnicalResult
from app.ai.technical.silence import LongSilenceDetector
from app.audio.analysis.schemas import AnalysisArtifact
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class TechnicalAnalyzer:
    """Compute technical outputs from shared analysis artifacts."""

    def __init__(
        self,
        *,
        silence: LongSilenceDetector,
        quality: AudioQualityAnalyzer,
        overlap: OverlapDetector,
    ) -> None:
        self._silence = silence
        self._quality = quality
        self._overlap = overlap

    def analyze(
        self,
        artifact: AnalysisArtifact,
        *,
        waveform: np.ndarray | None = None,
        sample_rate: int | None = None,
    ) -> TechnicalResult:
        long_silence_present, silence_details = self._silence.detect(artifact.vad)
        audio_quality, breakdown, quality_score = self._quality.score(
            artifact.features,
            artifact.vad,
        )

        bind = getattr(self._overlap, "bind_waveform", None)
        if bind is not None and waveform is not None:
            bind(waveform, sample_rate or artifact.sample_rate)

        overlap_present, overlap_score, overlap_details = self._overlap.detect(
            artifact.features,
            artifact.vad,
        )

        result = TechnicalResult(
            audio_id=artifact.audio_id,
            batch_id=artifact.batch_id,
            version=TECHNICAL_VERSION,
            audio_quality=audio_quality,
            speaker_overlap_present=overlap_present,
            long_silence_present=long_silence_present,
            quality_score=quality_score,
            quality_breakdown=breakdown,
            overlap_score=overlap_score,
            overlap_details=overlap_details,
            silence_details=silence_details,
        )
        logger.info(
            "technical_analysis_completed",
            audio_id=artifact.audio_id,
            audio_quality=audio_quality.value,
            speaker_overlap_present=overlap_present,
            long_silence_present=long_silence_present,
            quality_score=quality_score,
            status="ok",
        )
        return result
