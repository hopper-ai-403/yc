"""SER inference runtime: singleton model registry + label/intensity mapping.

The model is loaded once per worker process and reused for every inference.
Business logic never touches the singleton directly; it receives the model
via factory dependency injection.
"""

from __future__ import annotations

import math
import threading
from functools import lru_cache

import numpy as np

from app.ai.speech.mapping import LabelMappingEntry, load_label_mapping, parse_label_mapping
from app.ai.speech.model import ModelPrediction, SpeechEmotionModel
from app.config.settings import SpeechSettings
from app.shared.domain.enums import EmotionIntensity, EmotionTone
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_registry: dict[str, SpeechEmotionModel] = {}


def get_or_load_model(
    settings: SpeechSettings,
    *,
    model_factory: type[SpeechEmotionModel] | None = None,
) -> SpeechEmotionModel:
    """Return the process-wide singleton model, loading it once."""
    key = settings.model_name
    with _lock:
        model = _registry.get(key)
        if model is None:
            from app.ai.speech.model import HuggingFaceSpeechEmotionModel

            constructor = model_factory or HuggingFaceSpeechEmotionModel
            model = constructor(settings)  # type: ignore[call-arg]
            model.load()
            _registry[key] = model
            logger.info(
                "speech_model_singleton_registered",
                model_name=key,
                status="ok",
            )
        return model


def reset_model_registry() -> None:
    """Clear the singleton registry (tests only)."""
    with _lock:
        _registry.clear()
    get_resolved_label_mapping.cache_clear()


@lru_cache(maxsize=8)
def get_resolved_label_mapping(
    mapping_path: str,
    mapping_json: str,
) -> dict[str, LabelMappingEntry]:
    """Resolve label mapping: env/JSON override first, else file path."""
    if mapping_json.strip():
        import json

        try:
            raw = json.loads(mapping_json)
        except json.JSONDecodeError:
            raw = {}
        if isinstance(raw, dict) and raw:
            return parse_label_mapping(raw)
    return load_label_mapping(mapping_path or None)


def resolve_label_mapping(settings: SpeechSettings) -> dict[str, LabelMappingEntry]:
    """Return the active label mapping for the given settings."""
    override = ""
    if settings.label_mapping:
        import json

        override = json.dumps(settings.label_mapping, sort_keys=True)
    return get_resolved_label_mapping(settings.label_mapping_path, override)


def map_label(raw_label: str, settings: SpeechSettings) -> EmotionTone:
    """Map a raw model label to a platform tone. Unknown labels fall back."""
    mapping = resolve_label_mapping(settings)
    entry = mapping.get(raw_label.strip().lower())
    if entry is not None:
        return entry.emotion
    try:
        return EmotionTone(settings.unmapped_label_tone)
    except ValueError:
        return EmotionTone.NEUTRAL


def map_label_entry(
    raw_label: str, settings: SpeechSettings
) -> LabelMappingEntry | None:
    """Return the full mapping entry (emotion + weight) when present."""
    return resolve_label_mapping(settings).get(raw_label.strip().lower())


def select_tone(
    prediction: ModelPrediction, settings: SpeechSettings
) -> tuple[EmotionTone, dict[str, float]]:
    """Aggregate weighted mapped probabilities and pick the winning tone."""
    aggregated: dict[str, float] = {}
    for score in prediction.scores:
        entry = map_label_entry(score.label, settings)
        if entry is None:
            tone = map_label(score.label, settings)
            weight = 1.0
        else:
            tone = entry.emotion
            weight = entry.weight
        key = tone.value
        aggregated[key] = aggregated.get(key, 0.0) + score.probability * weight

    if not aggregated:
        fallback = map_label(prediction.top.label, settings)
        return fallback, {fallback.value: round(prediction.top.probability, 6)}

    winner = max(aggregated.items(), key=lambda item: item[1])[0]
    normalized = {
        key: round(value, 6) for key, value in sorted(aggregated.items(), key=lambda x: -x[1])
    }
    return EmotionTone(winner), normalized


def map_intensity(
    prediction: ModelPrediction | float,
    settings: SpeechSettings,
) -> EmotionIntensity:
    """Derive intensity from top probability, margin, and prediction entropy.

    Accepts a ``ModelPrediction`` (preferred) or a bare top-1 float for
    backward-compatible call sites / tests.
    """
    if isinstance(prediction, (int, float)):
        certainty = float(prediction)
    else:
        certainty = _prediction_certainty(prediction, settings)

    if certainty >= settings.intensity_high_probability:
        return EmotionIntensity.HIGH
    if certainty >= settings.intensity_medium_probability:
        return EmotionIntensity.MEDIUM
    return EmotionIntensity.LOW


def _prediction_certainty(
    prediction: ModelPrediction, settings: SpeechSettings
) -> float:
    """Combine top-1 probability, top-1/top-2 margin, and inverse entropy."""
    probs = np.asarray(
        [max(0.0, float(score.probability)) for score in prediction.scores],
        dtype=np.float64,
    )
    if probs.size == 0:
        return 0.0
    total = float(probs.sum())
    if total <= 0:
        return 0.0
    probs = probs / total
    order = np.argsort(probs)[::-1]
    top1 = float(probs[order[0]])
    top2 = float(probs[order[1]]) if probs.size > 1 else 0.0
    margin = max(0.0, top1 - top2)

    # Normalized entropy in [0, 1]; low entropy ⇒ high certainty.
    if probs.size == 1:
        entropy_norm = 0.0
    else:
        entropy = float(-np.sum(probs * np.log(probs + 1e-12)))
        entropy_norm = entropy / math.log(probs.size)

    inverse_entropy = 1.0 - entropy_norm
    certainty = (
        settings.intensity_top_weight * top1
        + settings.intensity_margin_weight * margin
        + settings.intensity_entropy_weight * inverse_entropy
    )
    weight_sum = (
        settings.intensity_top_weight
        + settings.intensity_margin_weight
        + settings.intensity_entropy_weight
    )
    if weight_sum > 0:
        certainty /= weight_sum
    return float(min(1.0, max(0.0, certainty)))
