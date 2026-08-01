"""Noise event label mapping (AudioSet / HF labels → platform NoiseType)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.ai.speech.mapping import resolve_config_path
from app.shared.domain.enums import NoiseType
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)

_VALID_TYPES = {noise.value for noise in NoiseType}


@dataclass(frozen=True)
class NoiseLabelMappingEntry:
    """One event-model label → platform noise type mapping."""

    noise_type: NoiseType
    weight: float = 1.0


def parse_noise_label_mapping(raw: dict[str, Any]) -> dict[str, NoiseLabelMappingEntry]:
    """Parse JSON mapping values into typed entries."""
    parsed: dict[str, NoiseLabelMappingEntry] = {}
    for key, value in raw.items():
        label = str(key).strip().lower()
        if not label:
            continue
        if isinstance(value, str):
            type_name = value.strip().upper()
            weight = 1.0
        elif isinstance(value, dict):
            type_name = str(value.get("type", "")).strip().upper()
            weight = float(value.get("weight", 1.0))
        else:
            continue
        if type_name not in _VALID_TYPES:
            logger.warning(
                "noise_label_mapping_skipped",
                label=label,
                noise_type=type_name,
                status="invalid_type",
            )
            continue
        parsed[label] = NoiseLabelMappingEntry(
            noise_type=NoiseType(type_name),
            weight=max(0.0, weight),
        )
    return parsed


def load_noise_label_mapping(path: str | None) -> dict[str, NoiseLabelMappingEntry]:
    """Load noise event mapping from JSON. Empty when missing."""
    if not path:
        return {}
    resolved = resolve_config_path(path)
    if not resolved.is_file():
        logger.warning(
            "noise_label_mapping_missing",
            path=str(resolved),
            status="missing",
        )
        return {}
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "noise_label_mapping_load_failed",
            path=str(resolved),
            error=str(exc),
            status="error",
        )
        return {}
    if not isinstance(payload, dict):
        return {}
    mapping = parse_noise_label_mapping(payload)
    logger.info(
        "noise_label_mapping_loaded",
        path=str(resolved),
        entries=len(mapping),
        status="ok",
    )
    return mapping
