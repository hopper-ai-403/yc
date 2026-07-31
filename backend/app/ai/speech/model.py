"""Pluggable Speech Emotion Recognition model interface.

Business logic never calls Hugging Face APIs directly; all model access goes
through the SpeechEmotionModel interface.
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from app.ai.speech.exceptions import SpeechInferenceException, SpeechModelException
from app.config.settings import SpeechSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class LabelScore(BaseModel):
    """One raw model label with its probability."""

    model_config = ConfigDict(frozen=True)

    label: str
    probability: float = Field(ge=0, le=1)


class ModelPrediction(BaseModel):
    """Raw prediction from an SER model (unmapped labels)."""

    model_config = ConfigDict(frozen=True)

    scores: list[LabelScore]

    @property
    def top(self) -> LabelScore:
        return max(self.scores, key=lambda s: s.probability)


class ModelMetadata(BaseModel):
    """Model descriptor exposed by metadata()."""

    model_config = ConfigDict(frozen=True)

    name: str
    backend: str
    labels: list[str] = Field(default_factory=list)
    expected_sample_rate: int = 16_000


class SpeechEmotionModel(Protocol):
    """Interface for speech emotion recognition models."""

    def load(self) -> None:
        """Load model weights. Called once per worker process."""

    def predict(self, waveform: np.ndarray, sample_rate: int) -> ModelPrediction:
        """Run inference over a mono float32 waveform."""

    def metadata(self) -> ModelMetadata:
        """Return model metadata."""


class HuggingFaceSpeechEmotionModel:
    """Default SER implementation backed by a Hugging Face audio classifier.

    transformers is imported lazily inside load() so worker startup and tests
    never pay the import cost or download weights until inference is required.
    """

    def __init__(self, settings: SpeechSettings) -> None:
        self._settings = settings
        self._pipeline: Any = None

    def load(self) -> None:
        if self._pipeline is not None:
            return
        try:
            from transformers import pipeline as hf_pipeline  # type: ignore[import-not-found]
        except ImportError as exc:
            raise SpeechModelException(
                "transformers is required for HuggingFaceSpeechEmotionModel",
                details={"error": str(exc)},
            ) from exc
        try:
            self._pipeline = hf_pipeline(
                "audio-classification",
                model=self._settings.model_name,
                device=self._settings.device,
            )
            logger.info(
                "speech_model_loaded",
                model_name=self._settings.model_name,
                status="ok",
            )
        except Exception as exc:
            raise SpeechModelException(
                "Failed to load Hugging Face SER model",
                details={"model": self._settings.model_name, "error": str(exc)},
            ) from exc

    def predict(self, waveform: np.ndarray, sample_rate: int) -> ModelPrediction:
        if self._pipeline is None:
            raise SpeechInferenceException(
                "Model not loaded; call load() before predict()",
            )
        try:
            outputs: Any = self._pipeline(
                {"raw": waveform, "sampling_rate": sample_rate},
                top_k=self._settings.top_k,
            )
            scores = [
                LabelScore(label=str(item["label"]), probability=float(item["score"]))
                for item in outputs
            ]
            if not scores:
                raise SpeechInferenceException("Model returned no scores")
            return ModelPrediction(scores=scores)
        except SpeechInferenceException:
            raise
        except Exception as exc:
            raise SpeechInferenceException(
                "Hugging Face SER inference failed",
                details={"error": str(exc)},
            ) from exc

    def metadata(self) -> ModelMetadata:
        labels: list[str] = []
        if self._pipeline is not None:
            id2label = getattr(self._pipeline.model.config, "id2label", None)
            if isinstance(id2label, dict):
                labels = [str(id2label[key]) for key in sorted(id2label)]
        return ModelMetadata(
            name=self._settings.model_name,
            backend="huggingface",
            labels=labels,
            expected_sample_rate=self._settings.expected_sample_rate,
        )
