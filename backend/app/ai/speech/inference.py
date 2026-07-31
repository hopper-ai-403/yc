"""SER inference runtime: singleton model registry + label/intensity mapping.

The model is loaded once per worker process and reused for every inference.
Business logic never touches the singleton directly; it receives the model
via factory dependency injection.
"""

from __future__ import annotations

import threading

from app.ai.speech.model import SpeechEmotionModel
from app.config.settings import SpeechSettings
from app.shared.domain.enums import EmotionIntensity, EmotionTone
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_registry: dict[str, SpeechEmotionModel] = {}


def get_or_load_model(
    settings: SpeechSettings,
    *,
    model_factory: "type[SpeechEmotionModel] | None" = None,
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


def map_label(raw_label: str, settings: SpeechSettings) -> EmotionTone:
    """Map a raw model label to a platform tone. Unknown labels fall back."""
    tone_value = settings.label_mapping.get(
        raw_label.strip().lower(),
        settings.unmapped_label_tone,
    )
    try:
        return EmotionTone(tone_value)
    except ValueError:
        return EmotionTone(settings.unmapped_label_tone)


def map_intensity(top_probability: float, settings: SpeechSettings) -> EmotionIntensity:
    """Derive calibrated intensity from the top-1 probability."""
    if top_probability >= settings.intensity_high_probability:
        return EmotionIntensity.HIGH
    if top_probability >= settings.intensity_medium_probability:
        return EmotionIntensity.MEDIUM
    return EmotionIntensity.LOW
