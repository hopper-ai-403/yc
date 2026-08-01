"""Offline SER model benchmark utility (does not alter production pipelines)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.ai.speech.inference import (
    map_intensity,
    reset_model_registry,
    select_tone,
)
from app.ai.speech.model import HuggingFaceSpeechEmotionModel, ModelPrediction
from app.config.settings import SpeechSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SerBenchmarkRow:
    """One model × audio evaluation row."""

    model_name: str
    audio_id: str
    raw_label: str
    emotional_tone: str
    emotional_intensity: str
    top_probability: float
    scores: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "audio_id": self.audio_id,
            "raw_label": self.raw_label,
            "emotional_tone": self.emotional_tone,
            "emotional_intensity": self.emotional_intensity,
            "top_probability": self.top_probability,
            "scores": self.scores,
        }


def evaluate_ser_models(
    *,
    waveforms: dict[str, tuple[np.ndarray, int]],
    model_names: list[str],
    base_settings: SpeechSettings | None = None,
) -> list[SerBenchmarkRow]:
    """Run multiple HF SER models over the same waveforms.

    Each model is loaded lazily via ``HuggingFaceSpeechEmotionModel`` and the
    existing mapping/intensity helpers — production business logic is untouched.
    """
    settings_template = base_settings or SpeechSettings()
    rows: list[SerBenchmarkRow] = []

    for model_name in model_names:
        reset_model_registry()
        settings = settings_template.model_copy(update={"model_name": model_name})
        model = HuggingFaceSpeechEmotionModel(settings)
        model.load()
        logger.info("ser_benchmark_model_ready", model_name=model_name, status="ok")

        for audio_id, (waveform, sample_rate) in waveforms.items():
            prediction: ModelPrediction = model.predict(waveform, sample_rate)
            tone, _aggregated = select_tone(prediction, settings)
            intensity = map_intensity(prediction, settings)
            rows.append(
                SerBenchmarkRow(
                    model_name=model_name,
                    audio_id=audio_id,
                    raw_label=prediction.top.label,
                    emotional_tone=tone.value,
                    emotional_intensity=intensity.value,
                    top_probability=round(prediction.top.probability, 6),
                    scores={
                        score.label: round(score.probability, 6)
                        for score in prediction.scores
                    },
                )
            )

    reset_model_registry()
    return rows
