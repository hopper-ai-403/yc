"""Audio normalizer coordinating ffmpeg conversion targets."""

from __future__ import annotations

from pathlib import Path

from app.audio.preprocessing.ffmpeg import FFmpegClient
from app.audio.preprocessing.validator import AudioValidator
from app.config.settings import PreprocessingSettings


class AudioNormalizer:
    """Normalize audio to the platform target format."""

    def __init__(
        self,
        settings: PreprocessingSettings,
        ffmpeg: FFmpegClient,
        validator: AudioValidator,
    ) -> None:
        self._settings = settings
        self._ffmpeg = ffmpeg
        self._validator = validator

    @property
    def target_sample_rate(self) -> int:
        return self._settings.target_sample_rate

    @property
    def target_channels(self) -> int:
        return self._settings.target_channels

    @property
    def target_codec(self) -> str:
        return "pcm_s16le"

    def normalize(self, input_path: Path, output_path: Path) -> Path:
        """Run conversion + loudness normalization; return output path."""
        self._ffmpeg.normalize(input_path, output_path)
        self._validator.validate_normalized_output(output_path)
        return output_path
