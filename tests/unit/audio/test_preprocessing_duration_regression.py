"""Regression: preprocessing must preserve conversational duration."""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from app.audio.preprocessing.ffmpeg import FFmpegClient
from app.audio.preprocessing.ffprobe import FFprobeClient
from app.config.settings import PreprocessingSettings

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe required for conversational duration regression",
)


def _probe_duration(ffprobe: FFprobeClient, path: Path) -> float:
    probe = ffprobe.probe(path)
    for stream in probe.streams:
        if (stream.codec_type or "").lower() == "audio" and stream.duration:
            return float(stream.duration)
    if probe.format is not None and probe.format.duration is not None:
        return float(probe.format.duration)
    raise AssertionError(f"Could not read duration for {path}")


def _synthesize_conversational_wav(path: Path, *, total_seconds: float = 45.0) -> None:
    """Create a 45s mono wav with mid-call silence (conversational pause).

    Layout: 10s tone → 3s silence → 10s tone → 3s silence → remainder tone.
    Aggressive mid-file silenceremove would collapse this to ~a few seconds.
    """
    # sine=... : silence : sine : silence : sine
    filter_graph = (
        "sine=frequency=440:sample_rate=16000:duration=10,"
        "aevalsrc=0:sample_rate=16000:duration=3,"
        "sine=frequency=440:sample_rate=16000:duration=10,"
        "aevalsrc=0:sample_rate=16000:duration=3,"
        f"sine=frequency=440:sample_rate=16000:duration={total_seconds - 26}"
    )
    # Use concat via filter_complex for reliable silence gaps.
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=16000:duration=10",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=16000:cl=mono:d=3",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=16000:duration=10",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=16000:cl=mono:d=3",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:sample_rate=16000:duration={total_seconds - 26}",
        "-filter_complex",
        "[0:a][1:a][2:a][3:a][4:a]concat=n=5:v=0:a=1[out]",
        "-map",
        "[out]",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(path),
    ]
    del filter_graph
    completed = subprocess.run(  # noqa: S603
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[:1500])


def test_preprocessing_does_not_collapse_conversational_recording() -> None:
    settings = PreprocessingSettings(trim_silence=False)
    ffmpeg = FFmpegClient(settings)
    ffprobe = FFprobeClient(settings)

    with tempfile.TemporaryDirectory(prefix="aip-preprocess-regress-") as tmp:
        tmp_dir = Path(tmp)
        original = tmp_dir / "conversational.wav"
        normalized = tmp_dir / "normalized.wav"
        _synthesize_conversational_wav(original, total_seconds=45.0)

        original_duration = _probe_duration(ffprobe, original)
        assert 30.0 <= original_duration <= 180.0

        ffmpeg.normalize(original, normalized)
        normalized_duration = _probe_duration(ffprobe, normalized)

        assert normalized_duration >= 1.0, (
            f"Normalized audio collapsed to {normalized_duration:.4f}s"
        )
        delta_ratio = abs(normalized_duration - original_duration) / original_duration
        assert delta_ratio <= settings.max_duration_delta_ratio + 1e-6, (
            f"Duration delta {delta_ratio:.4%} exceeds "
            f"±{settings.max_duration_delta_ratio:.0%} "
            f"(original={original_duration:.3f}s, "
            f"normalized={normalized_duration:.3f}s)"
        )
        assert math.isclose(
            normalized_duration,
            original_duration,
            rel_tol=settings.max_duration_delta_ratio,
        )


def test_edge_trim_preserves_mid_call_pauses() -> None:
    settings = PreprocessingSettings(trim_silence=True)
    ffmpeg = FFmpegClient(settings)
    ffprobe = FFprobeClient(settings)

    with tempfile.TemporaryDirectory(prefix="aip-preprocess-edge-") as tmp:
        tmp_dir = Path(tmp)
        original = tmp_dir / "conversational.wav"
        normalized = tmp_dir / "normalized.wav"
        _synthesize_conversational_wav(original, total_seconds=45.0)
        original_duration = _probe_duration(ffprobe, original)

        ffmpeg.normalize(original, normalized)
        normalized_duration = _probe_duration(ffprobe, normalized)

        # Edge-only trim may remove a little leading/trailing null, but must
        # not collapse a 45s call with internal pauses to a sub-second clip.
        assert normalized_duration >= 1.0
        assert normalized_duration >= original_duration * 0.5
