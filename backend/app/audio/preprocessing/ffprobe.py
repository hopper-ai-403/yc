"""ffprobe wrapper for audio stream inspection."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.audio.preprocessing.exceptions import (
    FFprobeException,
    PreprocessingTimeoutException,
)
from app.audio.preprocessing.metadata import ProbeResult
from app.config.settings import PreprocessingSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)


class FFprobeClient:
    """Runs ffprobe and returns structured probe results."""

    def __init__(self, settings: PreprocessingSettings) -> None:
        self._settings = settings
        self._binary = settings.ffprobe_path or shutil.which("ffprobe") or "ffprobe"

    def probe(self, path: Path) -> ProbeResult:
        """Inspect an audio file with ffprobe."""
        command = [
            self._binary,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            completed = subprocess.run(  # noqa: S603
                command,
                capture_output=True,
                text=True,
                timeout=self._settings.ffprobe_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PreprocessingTimeoutException(
                "ffprobe timed out",
                details={
                    "path": str(path),
                    "timeout": self._settings.ffprobe_timeout_seconds,
                },
            ) from exc
        except FileNotFoundError as exc:
            raise FFprobeException(
                "ffprobe binary not found",
                details={"binary": self._binary},
            ) from exc

        if completed.returncode != 0:
            raise FFprobeException(
                "ffprobe failed",
                details={
                    "returncode": completed.returncode,
                    "stderr": (completed.stderr or "")[:1000],
                    "path": str(path),
                },
            )

        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise FFprobeException(
                "ffprobe returned invalid JSON",
                details={"stdout": (completed.stdout or "")[:500]},
            ) from exc

        result = ProbeResult.model_validate(payload)
        logger.info(
            "metadata_extracted",
            path=str(path),
            streams=len(result.streams),
            status="ok",
        )
        return result
