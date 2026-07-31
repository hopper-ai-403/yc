"""Waveform loading and basic signal utilities."""

from __future__ import annotations

import io

import numpy as np

from app.audio.analysis.exceptions import InvalidWaveformException


def load_waveform(data: bytes, *, expected_sample_rate: int | None = None) -> tuple[np.ndarray, int]:
    """Load mono float32 waveform from WAV bytes."""
    if not data:
        raise InvalidWaveformException("Empty audio payload")

    try:
        import soundfile as sf
    except ImportError as exc:  # pragma: no cover
        raise InvalidWaveformException(
            "soundfile is required to load waveforms",
            details={"error": str(exc)},
        ) from exc

    try:
        audio, sample_rate = sf.read(io.BytesIO(data), always_2d=True, dtype="float32")
    except Exception as exc:
        raise InvalidWaveformException(
            "Failed to decode waveform",
            details={"error": str(exc)},
        ) from exc

    if audio.size == 0:
        raise InvalidWaveformException("Waveform contains no samples")

    mono = np.mean(audio, axis=1).astype(np.float32, copy=False)
    if not np.isfinite(mono).all():
        raise InvalidWaveformException("Waveform contains non-finite samples")

    if expected_sample_rate is not None and int(sample_rate) != expected_sample_rate:
        # Analysis expects preprocessed 16 kHz audio; do not resample here.
        raise InvalidWaveformException(
            "Unexpected sample rate for analysis input",
            details={
                "expected": expected_sample_rate,
                "actual": int(sample_rate),
            },
        )

    peak = float(np.max(np.abs(mono)))
    if peak <= 0:
        raise InvalidWaveformException("Silent or zero-amplitude waveform")

    return mono, int(sample_rate)


def frame_rms(waveform: np.ndarray, *, frame_length: int, hop_length: int) -> np.ndarray:
    """Compute per-frame RMS energy."""
    if waveform.size == 0:
        return np.zeros(0, dtype=np.float32)
    if frame_length <= 0 or hop_length <= 0:
        raise InvalidWaveformException("Invalid framing parameters")

    padded = np.pad(waveform, (0, max(0, frame_length - 1)), mode="constant")
    frames = np.lib.stride_tricks.sliding_window_view(padded, frame_length)[::hop_length]
    return np.sqrt(np.mean(np.square(frames), axis=1)).astype(np.float32)
