"""Speech analyzer: waveform → normalized emotion outputs."""

from __future__ import annotations

import numpy as np

from app.ai.speech.inference import map_intensity, map_label
from app.ai.speech.model import SpeechEmotionModel
from app.ai.speech.schemas import SPEECH_VERSION, SpeechResult
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
    ) -> SpeechResult:
        prediction = self._model.predict(waveform, sample_rate)
        top = prediction.top

        emotional_tone = map_label(top.label, self._settings)
        emotional_intensity = map_intensity(top.probability, self._settings)

        tone_probabilities: dict[str, float] = {}
        for score in prediction.scores:
            tone = map_label(score.label, self._settings)
            tone_probabilities[tone.value] = round(
                max(tone_probabilities.get(tone.value, 0.0), score.probability),
                6,
            )

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
            status="ok",
        )
        return result
