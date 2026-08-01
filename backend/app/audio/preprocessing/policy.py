"""Preprocessing policy fingerprint and stale-artifact detection.

Policy v2: never remove mid-call conversational pauses. Optional trim is
leading/trailing edges only.
"""

from __future__ import annotations

from typing import Any

from app.config.settings import PreprocessingSettings

# Bump when silence / duration semantics change so existing artifacts reprocess.
PREPROCESSING_POLICY_VERSION = "2.0.0"

# Conversational calls that collapse below this after normalize are always stale.
_COLLAPSED_DURATION_SECONDS = 1.0
_MIN_CONVERSATIONAL_SECONDS = 30.0


def trim_mode_for_settings(settings: PreprocessingSettings) -> str:
    return "edges" if settings.trim_silence else "none"


def preprocessing_fingerprint(settings: PreprocessingSettings) -> dict[str, Any]:
    """Fields persisted into metadata so future runs can detect drift."""
    return {
        "preprocessing_policy_version": PREPROCESSING_POLICY_VERSION,
        "trim_silence": settings.trim_silence,
        "trim_mode": trim_mode_for_settings(settings),
    }


def duration_delta_ratio(original: float, normalized: float) -> float:
    if original <= 0:
        return float("inf")
    return abs(normalized - original) / original


def is_duration_collapsed(
    original: float,
    normalized: float | None,
) -> bool:
    """True when a normal-length call was reduced to a sub-second clip."""
    if normalized is None:
        return True
    if (
        original >= _MIN_CONVERSATIONAL_SECONDS
        and normalized < _COLLAPSED_DURATION_SECONDS
    ):
        return True
    return False


def is_duration_out_of_tolerance(
    original: float,
    normalized: float | None,
    *,
    max_delta_ratio: float,
) -> bool:
    if normalized is None or original <= 0:
        return True
    return duration_delta_ratio(original, normalized) > max_delta_ratio


def is_preprocessing_stale(
    metadata: dict[str, Any] | None,
    settings: PreprocessingSettings,
) -> bool:
    """Return True when stored preprocess output must not be reused."""
    if not metadata:
        return True

    version = metadata.get("preprocessing_policy_version")
    if version != PREPROCESSING_POLICY_VERSION:
        return True

    stored_trim = bool(metadata.get("trim_silence", False))
    stored_mode = metadata.get("trim_mode")
    expected_mode = trim_mode_for_settings(settings)
    if stored_trim != settings.trim_silence or stored_mode != expected_mode:
        return True

    original = _as_float(metadata.get("duration"))
    normalized = _as_float(metadata.get("normalized_duration"))
    if original is None:
        return True
    if is_duration_collapsed(original, normalized):
        return True

    # Default path (no trim): reject anything outside ±max_duration_delta_ratio.
    if not settings.trim_silence:
        if is_duration_out_of_tolerance(
            original,
            normalized,
            max_delta_ratio=settings.max_duration_delta_ratio,
        ):
            return True

    return False


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
