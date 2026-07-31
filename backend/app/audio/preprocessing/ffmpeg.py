"""ffmpeg wrapper for conversion, loudness normalization, and level analysis."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from app.audio.preprocessing.exceptions import (
    FFmpegException,
    PreprocessingTimeoutException,
)
from app.config.settings import PreprocessingSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)

_MEAN_VOLUME_RE = re.compile(r"mean_volume:\s*([-\d.]+)\s*dB")
_MAX_VOLUME_RE = re.compile(r"max_volume:\s*([-\d.]+)\s*dB")


class FFmpegClient:
    """Runs ffmpeg for normalization and loudness measurement."""

    def __init__(self, settings: PreprocessingSettings) -> None:
        self._settings = settings
        self._binary = settings.ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"

    def measure_levels(self, path: Path) -> tuple[float | None, float | None]:
        """Return (peak_db, rms_db) using volumedetect."""
        command = [
            self._binary,
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ]
        completed = self._run(command, timeout=self._settings.ffmpeg_timeout_seconds)
        stderr = completed.stderr or ""
        peak_match = _MAX_VOLUME_RE.search(stderr)
        rms_match = _MEAN_VOLUME_RE.search(stderr)
        peak = float(peak_match.group(1)) if peak_match else None
        rms = float(rms_match.group(1)) if rms_match else None
        return peak, rms

    def normalize(
        self,
        input_path: Path,
        output_path: Path,
    ) -> None:
        """Convert to mono 16kHz 16-bit PCM WAV with optional silence trim + LUFS."""
        filters: list[str] = []
        if self._settings.trim_silence:
            filters.append(
                "silenceremove="
                f"start_periods=1:start_duration={self._settings.silence_min_duration_seconds}:"
                f"start_threshold={self._settings.silence_threshold_db}dB:"
                f"stop_periods=1:stop_duration={self._settings.silence_min_duration_seconds}:"
                f"stop_threshold={self._settings.silence_threshold_db}dB"
            )
        filters.append(
            "loudnorm="
            f"I={self._settings.target_lufs}:"
            f"TP={self._settings.target_true_peak_db}:"
            f"LRA={self._settings.loudness_range}"
        )
        filter_graph = ",".join(filters)

        command = [
            self._binary,
            "-y",
            "-hide_banner",
            "-i",
            str(input_path),
            "-vn",
            "-af",
            filter_graph,
            "-ac",
            str(self._settings.target_channels),
            "-ar",
            str(self._settings.target_sample_rate),
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(output_path),
        ]
        logger.info(
            "normalization_started",
            input=str(input_path),
            output=str(output_path),
            sample_rate=self._settings.target_sample_rate,
            channels=self._settings.target_channels,
        )
        self._run(command, timeout=self._settings.ffmpeg_timeout_seconds)
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise FFmpegException(
                "ffmpeg produced an empty normalized file",
                details={"output": str(output_path)},
            )
        logger.info(
            "normalization_finished",
            output=str(output_path),
            size_bytes=output_path.stat().st_size,
            status="ok",
        )

    def _run(
        self,
        command: list[str],
        *,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(  # noqa: S603
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PreprocessingTimeoutException(
                "ffmpeg timed out",
                details={"timeout": timeout, "command": command[:6]},
            ) from exc
        except FileNotFoundError as exc:
            raise FFmpegException(
                "ffmpeg binary not found",
                details={"binary": self._binary},
            ) from exc

        if completed.returncode != 0:
            raise FFmpegException(
                "ffmpeg failed",
                details={
                    "returncode": completed.returncode,
                    "stderr": (completed.stderr or "")[:1500],
                },
            )
        return completed
