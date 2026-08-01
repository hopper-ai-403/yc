"""Speech analyzer: waveform → normalized emotion outputs."""

from __future__ import annotations

import numpy as np

from app.ai.speech.inference import map_intensity, select_tone
from app.ai.speech.model import SpeechEmotionModel
from app.ai.speech.schemas import SPEECH_VERSION, SpeechResult
from app.audio.analysis.schemas import TimeSegment
from app.config.settings import SpeechSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class SpeechAnalyzer:
    """Run SER inference and normalize labels/intensity before persistence."""

    def __init__(
        self,
        *,
        model: SpeechEmotionModel,
        settings: SpeechSettings,
    ) -> None:
        self._model = model
        self._settings = settings

    def analyze(
        self,
        *,
        audio_id: str,
        batch_id: str,
        waveform: np.ndarray,
        sample_rate: int,
        speech_segments: list[TimeSegment] | None = None,
    ) -> SpeechResult:
        inference_wave = self._speech_gated_waveform(
            waveform, sample_rate, speech_segments
        )
        prediction = self._model.predict(inference_wave, sample_rate)
        top = prediction.top

        emotional_tone, tone_probabilities = select_tone(prediction, self._settings)
        emotional_intensity = map_intensity(prediction, self._settings)

        result = SpeechResult(
            audio_id=audio_id,
            batch_id=batch_id,
            version=SPEECH_VERSION,
            emotional_tone=emotional_tone,
            emotional_intensity=emotional_intensity,
            top_probability=round(top.probability, 6),
            tone_probabilities=tone_probabilities,
            model_name=self._model.metadata().name,
            raw_label=top.label,
        )
        logger.info(
            "speech_analysis_completed",
            audio_id=audio_id,
            emotional_tone=emotional_tone.value,
            emotional_intensity=emotional_intensity.value,
            top_probability=top.probability,
            raw_label=top.label,
            speech_gated=bool(speech_segments),
            status="ok",
        )
        return result

    def _speech_gated_waveform(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        speech_segments: list[TimeSegment] | None,
    ) -> np.ndarray:
        """Restrict SER to VAD speech regions when available.

        SER models trained on short utterances are polluted by long silence
        and background beds on call recordings. Concatenating speech segments
        is generic (no filename special-casing). Falls back to the full
        waveform when segments are missing or too short.
        """
        if not speech_segments:
            return waveform
        pieces: list[np.ndarray] = []
        min_samples = max(1, int(self._settings.chunk_min_seconds * sample_rate))
        for segment in speech_segments:
            start = int(segment.start * sample_rate)
            end = int(segment.end * sample_rate)
            if end - start < 1:
                continue
            pieces.append(waveform[start:end])
        if not pieces:
            return waveform
        gated = np.concatenate(pieces)
        if len(gated) < min_samples:
            return waveform
        return gated
