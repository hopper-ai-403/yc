"""Configurable speech label mapping loaded from JSON (no hardcoded labels)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.shared.domain.enums import EmotionTone
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)

_VALID_TONES = {tone.value for tone in EmotionTone}


@dataclass(frozen=True)
class LabelMappingEntry:
    """One raw-model-label → platform emotion mapping."""

    emotion: EmotionTone
    weight: float = 1.0


def resolve_config_path(path: str) -> Path:
    """Resolve a mapping file path against cwd and known project roots."""
    candidate = Path(path)
    if candidate.is_file():
        return candidate
    here = Path(__file__).resolve()
    roots = [
        Path.cwd(),
        here.parents[4],  # repo root (…/backend/app/ai/speech/mapping.py)
        here.parents[3],  # backend/
    ]
    for root in roots:
        resolved = (root / path).resolve()
        if resolved.is_file():
            return resolved
    return candidate


def parse_label_mapping(raw: dict[str, Any]) -> dict[str, LabelMappingEntry]:
    """Parse JSON mapping values into typed entries."""
    parsed: dict[str, LabelMappingEntry] = {}
    for key, value in raw.items():
        label = str(key).strip().lower()
        if not label:
            continue
        if isinstance(value, str):
            emotion_name = value.strip().upper()
            weight = 1.0
        elif isinstance(value, dict):
            emotion_name = str(value.get("emotion", "")).strip().upper()
            weight = float(value.get("weight", 1.0))
        else:
            continue
        if emotion_name not in _VALID_TONES:
            logger.warning(
                "speech_label_mapping_skipped",
                label=label,
                emotion=emotion_name,
                status="invalid_emotion",
            )
            continue
        parsed[label] = LabelMappingEntry(
            emotion=EmotionTone(emotion_name),
            weight=max(0.0, weight),
        )
    return parsed


def load_label_mapping(path: str | None) -> dict[str, LabelMappingEntry]:
    """Load mapping from a JSON file. Empty dict when path missing/unreadable."""
    if not path:
        return {}
    resolved = resolve_config_path(path)
    if not resolved.is_file():
        logger.warning(
            "speech_label_mapping_missing",
            path=str(resolved),
            status="missing",
        )
        return {}
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "speech_label_mapping_load_failed",
            path=str(resolved),
            error=str(exc),
            status="error",
        )
        return {}
    if not isinstance(payload, dict):
        return {}
    mapping = parse_label_mapping(payload)
    logger.info(
        "speech_label_mapping_loaded",
        path=str(resolved),
        entries=len(mapping),
        status="ok",
    )
    return mapping
