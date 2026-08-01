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
from app.audio.analysis.schemas import SignalFeatures, TimeSegment, VADResult
from app.config.settings import AcousticSettings
from app.shared.domain.enums import NoiseType
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_pipeline_registry: dict[str, Any] = {}

# Telephony / primary-speech labels describe the call channel, not background
# environment. When classifying non-speech regions they are suppressed so
# weaker media/static evidence (TV beds, hiss) can surface.
_CHANNEL_ARTIFACT_LABELS = frozenset(
    {
        "speech",
        "male speech, man speaking",
        "female speech, woman speaking",
        "child speech, kid speaking",
        "whispering",
        "silence",
        "telephone",
        "telephone dialing, dtmf",
        "telephone bell ringing",
        "dial tone",
        "busy signal",
        "sidetone",
    }
)

# Silence-region AST often confuses sharp static / room noise with transient
# office events. Require a higher score before accepting these types from
# silence clips; otherwise fall back to full-waveform classification.
_SILENCE_MIN_SCORE_BY_TYPE = {
    NoiseType.KEYBOARD.value: 0.35,
    NoiseType.OTHER.value: 0.12,
    NoiseType.WIND.value: 0.12,
    NoiseType.MUSIC.value: 0.08,
}


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

    Also exposes ``event_presence_evidence`` so the acoustic analyzer can use
    model-detected background events as noise-presence evidence when the
    signal-level detector alone is inconclusive. Inference runs at most once
    per bound waveform (cached until the waveform is cleared).

    When VAD silence segments are bound, inference prefers those non-speech
    regions (background beds) and suppresses telephony channel labels.
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
        self._silence_segments: list[TimeSegment] = []
        self._cached: tuple[dict[str, float], dict[str, float]] | None = None
        self._mapping = self._load_mapping(settings)
        self._used_silence_regions = False
        self._force_full_waveform = False

    @staticmethod
    def _load_mapping(settings: AcousticSettings) -> dict[str, NoiseLabelMappingEntry]:
        if settings.event_label_mapping:
            return parse_noise_label_mapping(settings.event_label_mapping)
        return load_noise_label_mapping(settings.event_label_mapping_path)

    def bind_waveform(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        *,
        vad: VADResult | None = None,
    ) -> None:
        """Attach a mono float waveform (and optional VAD) for evidence/classify."""
        self._waveform = np.asarray(waveform, dtype=np.float32)
        self._sample_rate = int(sample_rate)
        self._silence_segments = list(vad.silence_segments) if vad is not None else []
        self._cached = None
        self._used_silence_regions = False
        self._force_full_waveform = False

    def clear_waveform(self) -> None:
        self._waveform = None
        self._sample_rate = None
        self._silence_segments = []
        self._cached = None
        self._used_silence_regions = False
        self._force_full_waveform = False

    def _build_clips(self) -> list[np.ndarray]:
        """Prefer non-speech regions; fall back to full-waveform chunks."""
        assert self._waveform is not None and self._sample_rate is not None
        waveform = self._waveform
        sample_rate = self._sample_rate
        min_samples = max(1, int(self._settings.event_silence_min_seconds * sample_rate))
        max_clip = max(
            min_samples,
            int(self._settings.event_silence_max_clip_seconds * sample_rate),
        )
        max_total = max(
            min_samples,
            int(self._settings.event_silence_max_total_seconds * sample_rate),
        )

        if not self._force_full_waveform:
            clips: list[np.ndarray] = []
            total = 0
            for segment in self._silence_segments:
                if total >= max_total:
                    break
                start = int(segment.start * sample_rate)
                end = int(segment.end * sample_rate)
                if end - start < min_samples:
                    continue
                clip = waveform[start:end]
                if len(clip) > max_clip:
                    clip = clip[:max_clip]
                remaining = max_total - total
                if len(clip) > remaining:
                    clip = clip[:remaining]
                if len(clip) >= min_samples:
                    clips.append(clip)
                    total += len(clip)

            if clips:
                self._used_silence_regions = True
                return clips

        self._used_silence_regions = False
        # Full-file fallback: fixed windows so long calls do not collapse to one pass.
        chunk = max(min_samples, int(10.0 * sample_rate))
        if len(waveform) <= chunk:
            return [waveform]
        windows: list[np.ndarray] = []
        total = 0
        for start in range(0, len(waveform), chunk):
            if total >= max_total:
                break
            clip = waveform[start : start + chunk]
            if len(clip) < min_samples:
                continue
            windows.append(clip)
            total += len(clip)
        return windows or [waveform]

    def _run_events(self) -> tuple[dict[str, float], dict[str, float]] | None:
        """Run AST over clips; returns (aggregated, details).

        ``aggregated`` maps NoiseType values to summed weighted scores.
        Per-label scores use max-pooling across clips so sparse background
        events (e.g. a burst of static) are not drowned by unrelated segments.
        Returns None when no waveform is bound or inference fails.
        """
        if self._cached is not None:
            return self._cached
        if self._waveform is None or self._sample_rate is None:
            return None
        clip_count = 0
        label_max: dict[str, float] = {}
        try:
            pipe = _get_or_load_event_pipeline(
                self._settings.event_model_name,
                self._settings.event_device,
            )
            clips = self._build_clips()
            clip_count = len(clips)
            for clip in clips:
                outputs: Any = pipe(
                    {"raw": clip, "sampling_rate": self._sample_rate},
                    top_k=self._settings.event_top_k,
                )
                if not outputs:
                    continue
                for item in outputs:
                    label = str(item["label"])
                    score = float(item["score"])
                    prev = label_max.get(label, 0.0)
                    if score > prev:
                        label_max[label] = score
        except NoiseClassificationException:
            raise
        except Exception as exc:
            logger.warning(
                "noise_event_inference_failed",
                error=str(exc),
                status="error",
            )
            return None
        if not label_max:
            return None

        suppress_channel = self._used_silence_regions
        aggregated: dict[str, float] = {}
        details: dict[str, float] = {
            "silence_region_mode": 1.0 if suppress_channel else 0.0,
            "clip_count": float(clip_count),
        }
        for label, score in label_max.items():
            details[f"raw::{label}"] = round(score, 6)
            if score < self._settings.event_min_score:
                continue
            key_lower = label.strip().lower()
            if suppress_channel and key_lower in _CHANNEL_ARTIFACT_LABELS:
                details[f"suppressed::{label}"] = round(score, 6)
                continue
            entry = self._mapping.get(key_lower)
            if entry is None:
                continue
            type_key = entry.noise_type.value
            aggregated[type_key] = aggregated.get(type_key, 0.0) + score * entry.weight

        self._cached = (aggregated, details)
        return self._cached

    def event_presence_evidence(self) -> tuple[float, bool]:
        """Strongest mapped non-NONE event score and whether it implies noise.

        Used by the acoustic analyzer to rescue noise presence when the
        signal-level detector under-fires (e.g. steady TV/static beds that
        barely move broadband SNR). Purely model-driven and threshold-gated;
        never keyed to specific inputs.
        """
        result = self._run_events()
        if result is None:
            return 0.0, False
        aggregated, _ = result
        best = max(
            (
                score
                for key, score in aggregated.items()
                if key != NoiseType.NONE.value and score > 0
            ),
            default=0.0,
        )
        meets = best >= self._settings.event_presence_score
        if meets:
            logger.info(
                "noise_event_presence_evidence",
                evidence_score=round(best, 6),
                threshold=self._settings.event_presence_score,
                status="ok",
            )
        return round(best, 6), meets

    def classify(
        self,
        features: SignalFeatures,
        vad: VADResult,
    ) -> tuple[NoiseType, dict[str, float]]:
        try:
            result = self._run_events()
            if result is None:
                logger.info(
                    "noise_event_classifier_fallback",
                    reason=(
                        "missing_waveform"
                        if self._waveform is None
                        else "inference_unavailable"
                    ),
                    status="fallback",
                )
                return self._fallback.classify(features, vad)

            aggregated, details = result
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
            winner_score = candidates[winner]
            if self._used_silence_regions:
                min_score = _SILENCE_MIN_SCORE_BY_TYPE.get(
                    winner, self._settings.event_min_score
                )
                if winner_score < min_score and self._silence_segments:
                    logger.info(
                        "noise_event_silence_fallback_full",
                        background_noise_type=winner,
                        aggregated_score=round(winner_score, 6),
                        min_score=min_score,
                        status="fallback",
                    )
                    self._cached = None
                    self._force_full_waveform = True
                    result = self._run_events()
                    if result is not None:
                        aggregated, details = result
                        candidates = {
                            key: score
                            for key, score in aggregated.items()
                            if key != NoiseType.NONE.value and score > 0
                        }
                        if candidates:
                            winner = max(candidates.items(), key=lambda kv: kv[1])[0]
                            winner_score = candidates[winner]

            noise_type = NoiseType(winner)
            details = dict(details)
            details["aggregated_score"] = round(winner_score, 6)
            details["backend"] = 1.0  # marker: HF path used
            logger.info(
                "noise_classified",
                background_noise_type=noise_type.value,
                backend="audio_event",
                silence_region_mode=self._used_silence_regions,
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
