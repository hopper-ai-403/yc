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
        ...

    def predict(self, waveform: np.ndarray, sample_rate: int) -> ModelPrediction:
        """Run inference over a mono float32 waveform."""
        ...

    def metadata(self) -> ModelMetadata:
        """Return model metadata."""
        ...


class NeutralStubSpeechEmotionModel:
    """Zero-weight SER stub for memory-constrained workers (e.g. 1 GB free tier).

    Emits a deterministic NEUTRAL / neu prediction without loading Torch or
    Hugging Face weights. Use when ``SPEECH_ENABLED=false``.
    """

    def __init__(self, settings: SpeechSettings) -> None:
        self._settings = settings

    def load(self) -> None:
        logger.info(
            "speech_model_loaded",
            model_name="neutral-stub",
            backend="stub",
            status="ok",
        )

    def predict(self, waveform: np.ndarray, sample_rate: int) -> ModelPrediction:
        _ = waveform, sample_rate
        return ModelPrediction(
            scores=[LabelScore(label="neu", probability=1.0)],
        )

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            name="neutral-stub",
            backend="stub",
            labels=["neu"],
            expected_sample_rate=self._settings.expected_sample_rate,
        )


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
            from transformers import (
                pipeline as hf_pipeline,  # type: ignore[import-not-found]
            )
        except ImportError as exc:
            raise SpeechModelException(
                "transformers is required for HuggingFaceSpeechEmotionModel",
                details={"error": str(exc)},
            ) from exc
        try:
            import torch

            # Bound CPU thread pools so Railway workers don't balloon RAM.
            torch.set_num_threads(max(1, min(2, torch.get_num_threads())))
        except Exception:
            pass
        try:
            device = self._settings.device
            pipeline_kwargs: dict[str, Any] = {
                "model": self._settings.model_name,
                "device": device if device != "cpu" else -1,
                "model_kwargs": {"low_cpu_mem_usage": True},
            }
            self._pipeline = hf_pipeline("audio-classification", **pipeline_kwargs)
            logger.info(
                "speech_model_loaded",
                model_name=self._settings.model_name,
                device=device,
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
            chunks = self._split_chunks(waveform, sample_rate)
            accumulated: dict[str, float] = {}
            total_weight = 0.0
            for chunk in chunks:
                outputs: Any = self._pipeline(
                    {"raw": chunk, "sampling_rate": sample_rate},
                    top_k=self._settings.top_k,
                )
                if not outputs:
                    continue
                weight = float(len(chunk))
                total_weight += weight
                for item in outputs:
                    label = str(item["label"])
                    accumulated[label] = (
                        accumulated.get(label, 0.0) + float(item["score"]) * weight
                    )
            if not accumulated or total_weight <= 0:
                raise SpeechInferenceException("Model returned no scores")
            scores = [
                LabelScore(
                    label=label,
                    probability=min(1.0, max(0.0, value / total_weight)),
                )
                for label, value in accumulated.items()
            ]
            return ModelPrediction(scores=scores)
        except SpeechInferenceException:
            raise
        except Exception as exc:
            raise SpeechInferenceException(
                "Hugging Face SER inference failed",
                details={"error": str(exc)},
            ) from exc

    def _split_chunks(
        self, waveform: np.ndarray, sample_rate: int
    ) -> list[np.ndarray]:
        """Split long audio into fixed windows for chunked inference.

        SER models are trained on short utterances, so probabilities from a
        single pass over a multi-minute call are unreliable. Chunk-level
        predictions are averaged weighted by chunk duration. Disabled when
        chunk_seconds <= 0 or the waveform fits in one window.
        """
        chunk_seconds = self._settings.chunk_seconds
        chunk_samples = int(chunk_seconds * sample_rate)
        if chunk_seconds <= 0 or len(waveform) <= chunk_samples:
            return [waveform]
        min_samples = int(self._settings.chunk_min_seconds * sample_rate)
        chunks: list[np.ndarray] = []
        for start in range(0, len(waveform), chunk_samples):
            chunk = waveform[start : start + chunk_samples]
            if len(chunk) >= max(1, min_samples):
                chunks.append(chunk)
        return chunks or [waveform]

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
