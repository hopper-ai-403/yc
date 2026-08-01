"""Worker boot model warmup.

Loads singleton AI models during worker startup so the first task does not
pay model load latency. Tracks load time and exposes readiness state.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.config.settings import PerformanceSettings, SpeechSettings, TechnicalSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


@dataclass
class ModelWarmupState:
    """Process-wide warmup status used by health and system metrics."""

    warmup_enabled: bool = True
    loaded_models: list[str] = field(default_factory=list)
    load_durations_ms: dict[str, float] = field(default_factory=dict)

    @property
    def all_loaded(self) -> bool:
        return bool(self.loaded_models) or not self.warmup_enabled


_warmup_state = ModelWarmupState()


def get_warmup_state() -> ModelWarmupState:
    return _warmup_state


def reset_warmup_state() -> None:
    """Reset warmup state (tests only)."""
    _warmup_state.loaded_models.clear()
    _warmup_state.load_durations_ms.clear()


def warmup_models(
    speech: SpeechSettings,
    performance: PerformanceSettings,
    *,
    model_factory: type | None = None,
    technical: TechnicalSettings | None = None,
) -> ModelWarmupState:
    """Load singleton models at worker boot; measure load time per model."""
    _warmup_state.warmup_enabled = performance.model_warmup
    if not performance.model_warmup:
        logger.info("model_warmup_skipped", status="disabled")
        return _warmup_state

    from app.ai.speech.inference import get_or_load_model

    started = time.perf_counter()
    get_or_load_model(speech, model_factory=model_factory)
    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)

    _warmup_state.loaded_models.append(speech.model_name)
    _warmup_state.load_durations_ms[speech.model_name] = duration_ms
    logger.info(
        "model_warmup_completed",
        model_name=speech.model_name,
        load_duration_ms=duration_ms,
        status="ok",
    )

    if technical is not None:
        _warmup_overlap(technical)

    return _warmup_state


def _warmup_overlap(technical: TechnicalSettings) -> None:
    """Best-effort warm of the pyannote overlap singleton (never raises)."""
    backend = (technical.overlap_backend or "pyannote").strip().lower()
    if backend != "pyannote":
        return

    from app.ai.technical.overlap_model import (
        get_or_load_overlap_pipeline,
        pyannote_dependency_available,
    )

    if not pyannote_dependency_available():
        logger.info(
            "overlap_model_warmup_skipped",
            reason="dependency_missing",
            status="fallback",
        )
        return

    started = time.perf_counter()
    try:
        get_or_load_overlap_pipeline(technical)
    except Exception as exc:
        logger.warning(
            "overlap_model_warmup_failed",
            model_name=technical.overlap_model_name,
            error=str(exc),
            status="fallback",
        )
        return

    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
    _warmup_state.loaded_models.append(technical.overlap_model_name)
    _warmup_state.load_durations_ms[technical.overlap_model_name] = duration_ms
    logger.info(
        "overlap_model_warmup_completed",
        model_name=technical.overlap_model_name,
        load_duration_ms=duration_ms,
        backend="pyannote",
        status="ok",
    )


def is_model_loaded(model_name: str) -> bool:
    if not _warmup_state.warmup_enabled:
        return True
    return model_name in _warmup_state.loaded_models
