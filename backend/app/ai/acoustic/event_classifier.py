"""Hugging Face audio-event noise classification with heuristic fallback."""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

from app.ai.acoustic.classifier import HeuristicNoiseClassifier, NoiseClassifier
from app.ai.acoustic.exceptions import NoiseClassificationException
from app.ai.acoustic.mapping import (
    NoiseLabelMappingEntry,
    load_noise_label_mapping,
    parse_noise_label_mapping,
)
from app.audio.analysis.schemas import SignalFeatures, VADResult
from app.config.settings import AcousticSettings
from app.shared.domain.enums import NoiseType
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_pipeline_registry: dict[str, Any] = {}


def reset_event_model_registry() -> None:
    """Clear HF event-model singletons (tests only)."""
    with _lock:
        _pipeline_registry.clear()


def _get_or_load_event_pipeline(model_name: str, device: str) -> Any:
    with _lock:
        cached = _pipeline_registry.get(model_name)
        if cached is not None:
            return cached
        try:
            from transformers import (
                pipeline as hf_pipeline,  # type: ignore[import-not-found]
            )
        except ImportError as exc:
            raise NoiseClassificationException(
                "transformers is required for HuggingFaceAudioEventClassifier",
                details={"error": str(exc)},
            ) from exc
        try:
            pipe = hf_pipeline(
                "audio-classification",
                model=model_name,
                device=device,
            )
        except Exception as exc:
            raise NoiseClassificationException(
                "Failed to load Hugging Face audio-event model",
                details={"model": model_name, "error": str(exc)},
            ) from exc
        _pipeline_registry[model_name] = pipe
        logger.info(
            "noise_event_model_loaded",
            model_name=model_name,
            status="ok",
        )
        return pipe


class HuggingFaceAudioEventClassifier:
    """Audio-event classification via Hugging Face, with heuristic fallback.

    Implements ``NoiseClassifier``. Waveform is optional: call
    ``bind_waveform`` before ``classify`` when raw audio is available.
    Without a waveform, classification falls back to ``HeuristicNoiseClassifier``.
    """

    def __init__(
        self,
        settings: AcousticSettings,
        *,
        fallback: NoiseClassifier | None = None,
    ) -> None:
        self._settings = settings
        self._fallback = fallback or HeuristicNoiseClassifier(settings)
        self._waveform: np.ndarray | None = None
        self._sample_rate: int | None = None
        self._mapping = self._load_mapping(settings)

    @staticmethod
    def _load_mapping(settings: AcousticSettings) -> dict[str, NoiseLabelMappingEntry]:
        if settings.event_label_mapping:
            return parse_noise_label_mapping(settings.event_label_mapping)
        return load_noise_label_mapping(settings.event_label_mapping_path)

    def bind_waveform(self, waveform: np.ndarray, sample_rate: int) -> None:
        """Attach a mono float waveform for the next classify() call."""
        self._waveform = np.asarray(waveform, dtype=np.float32)
        self._sample_rate = int(sample_rate)

    def clear_waveform(self) -> None:
        self._waveform = None
        self._sample_rate = None

    def classify(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[NoiseType, dict[str, float]]:
        if self._waveform is None or self._sample_rate is None:
            logger.info(
                "noise_event_classifier_fallback",
                reason="missing_waveform",
                status="fallback",
            )
            return self._fallback.classify(features, vad)

        try:
            pipe = _get_or_load_event_pipeline(
                self._settings.event_model_name,
                self._settings.event_device,
            )
            outputs: Any = pipe(
                {"raw": self._waveform, "sampling_rate": self._sample_rate},
                top_k=self._settings.event_top_k,
            )
            if not outputs:
                return self._fallback.classify(features, vad)

            aggregated: dict[str, float] = {}
            details: dict[str, float] = {}
            for item in outputs:
                label = str(item["label"])
                score = float(item["score"])
                details[f"raw::{label}"] = round(score, 6)
                if score < self._settings.event_min_score:
                    continue
                entry = self._mapping.get(label.strip().lower())
                if entry is None:
                    continue
                key = entry.noise_type.value
                aggregated[key] = aggregated.get(key, 0.0) + score * entry.weight

            if not aggregated:
                logger.info(
                    "noise_event_classifier_fallback",
                    reason="no_mapped_labels",
                    status="fallback",
                )
                return self._fallback.classify(features, vad)

            # NONE is used to nullify content labels (e.g. primary Speech); never
            # select it as a background-noise type when other mapped events exist.
            candidates = {
                key: score
                for key, score in aggregated.items()
                if key != NoiseType.NONE.value and score > 0
            }
            if not candidates:
                logger.info(
                    "noise_event_classifier_fallback",
                    reason="only_none_mapped",
                    status="fallback",
                )
                return self._fallback.classify(features, vad)

            winner = max(candidates.items(), key=lambda kv: kv[1])[0]
            noise_type = NoiseType(winner)
            details["aggregated_score"] = round(candidates[winner], 6)
            details["backend"] = 1.0  # marker: HF path used
            logger.info(
                "noise_classified",
                background_noise_type=noise_type.value,
                backend="audio_event",
                status="ok",
            )
            return noise_type, details
        except NoiseClassificationException:
            raise
        except Exception as exc:
            logger.warning(
                "noise_event_classifier_fallback",
                reason="inference_error",
                error=str(exc),
                status="fallback",
            )
            return self._fallback.classify(features, vad)
        finally:
            self.clear_waveform()
