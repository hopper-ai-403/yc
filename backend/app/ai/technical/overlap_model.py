"""Lazy singleton registry for the pyannote overlap pipeline.

Mirrors the SER ``get_or_load_model`` pattern: one load per worker process,
keyed by model name. Business logic never touches this registry directly.
"""

from __future__ import annotations

import threading
from typing import Any

from app.config.settings import TechnicalSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_registry: dict[str, Any] = {}
_load_errors: dict[str, str] = {}


def pyannote_dependency_available() -> bool:
    """Return True when pyannote.audio can be imported."""
    try:
        import pyannote.audio  # noqa: F401
    except ImportError:
        return False
    return True


def get_or_load_overlap_pipeline(
    settings: TechnicalSettings,
    *,
    pipeline_factory: Any | None = None,
) -> Any:
    """Return the process-wide singleton overlap pipeline, loading it once."""
    key = settings.overlap_model_name
    with _lock:
        existing = _registry.get(key)
        if existing is not None:
            return existing
        if key in _load_errors and pipeline_factory is None:
            raise RuntimeError(_load_errors[key])

        try:
            pipeline = (
                pipeline_factory(settings)
                if pipeline_factory is not None
                else _load_default_pipeline(settings)
            )
        except Exception as exc:
            _load_errors[key] = str(exc)
            raise

        _registry[key] = pipeline
        _load_errors.pop(key, None)
        logger.info(
            "overlap_model_singleton_registered",
            model_name=key,
            backend="pyannote",
            status="ok",
        )
        return pipeline


def reset_overlap_model_registry() -> None:
    """Clear the singleton registry (tests only)."""
    with _lock:
        _registry.clear()
        _load_errors.clear()


def overlap_pipeline_loaded(model_name: str) -> bool:
    with _lock:
        return model_name in _registry


def _load_default_pipeline(settings: TechnicalSettings) -> Any:
    if not pyannote_dependency_available():
        raise RuntimeError("pyannote.audio is not installed")

    from pyannote.audio import Pipeline  # type: ignore[import-not-found]

    token = settings.overlap_hf_token
    kwargs: dict[str, Any] = {}
    if token:
        # pyannote.audio 3.x uses ``token``; older releases used ``use_auth_token``.
        kwargs["token"] = token

    try:
        pipeline = Pipeline.from_pretrained(settings.overlap_model_name, **kwargs)
    except TypeError:
        # Fallback for older pyannote releases.
        if token:
            pipeline = Pipeline.from_pretrained(
                settings.overlap_model_name,
                use_auth_token=token,
            )
        else:
            pipeline = Pipeline.from_pretrained(settings.overlap_model_name)

    if pipeline is None:
        raise RuntimeError(
            f"Pipeline.from_pretrained returned None for {settings.overlap_model_name}; "
            "check Hugging Face authentication / model access"
        )

    device = (settings.overlap_device or "cpu").strip().lower()
    try:
        import torch

        if device == "cuda" and torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
        else:
            pipeline.to(torch.device("cpu"))
    except Exception as exc:
        logger.warning(
            "overlap_model_device_move_failed",
            device=device,
            error=str(exc),
            status="fallback",
        )

    logger.info(
        "overlap_model_loaded",
        model_name=settings.overlap_model_name,
        model_version=settings.overlap_model_name,
        device=device,
        backend="pyannote",
        status="ok",
    )
    return pipeline
