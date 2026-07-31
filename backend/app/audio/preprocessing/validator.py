"""Audio file validation before normalization."""

from __future__ import annotations

from pathlib import Path

from app.audio.preprocessing.exceptions import AudioValidationException
from app.audio.preprocessing.metadata import ProbeResult
from app.config.settings import PreprocessingSettings
from app.shared.logging.setup import get_logger

logger = get_logger(__name__)

# Codecs accepted for call-center / upload formats (wav/mp3/ogg + common variants).
_DEFAULT_ALLOWED_CODECS = frozenset(
    {
        "pcm_s16le",
        "pcm_s24le",
        "pcm_s32le",
        "pcm_f32le",
        "pcm_u8",
        "pcm_mulaw",
        "pcm_alaw",
        "flac",
        "mp3",
        "mp3float",
        "aac",
        "vorbis",
        "opus",
        "opus_in_ogg",
    }
)


class AudioValidator:
    """Rejects unusable audio before spending normalize CPU."""

    def __init__(self, settings: PreprocessingSettings) -> None:
        self._settings = settings
        allowed = settings.allowed_codecs or sorted(_DEFAULT_ALLOWED_CODECS)
        self._allowed_codecs = {codec.lower() for codec in allowed}

    def validate_file_bytes(self, data: bytes, *, filename: str) -> None:
        if not data:
            raise AudioValidationException(
                "Zero-byte audio file rejected",
                details={"filename": filename},
            )
        if len(data) < 12:
            raise AudioValidationException(
                "Invalid audio header (file too small)",
                details={"filename": filename, "size": len(data)},
            )

    def validate_probe(self, probe: ProbeResult, *, path: Path) -> None:
        audio_streams = [
            stream
            for stream in probe.streams
            if (stream.codec_type or "").lower() == "audio"
        ]
        if not audio_streams:
            raise AudioValidationException(
                "Missing audio streams",
                details={"path": str(path)},
            )

        stream = audio_streams[0]
        codec = (stream.codec_name or "").lower()
        if not codec:
            raise AudioValidationException(
                "Unsupported or missing codec",
                details={"path": str(path)},
            )
        if codec not in self._allowed_codecs and not codec.startswith("pcm_"):
            raise AudioValidationException(
                "Unsupported codec",
                details={"codec": codec, "path": str(path)},
            )

        duration = self._as_float(stream.duration)
        if duration is None and probe.format is not None:
            duration = self._as_float(probe.format.duration)
        if duration is None or duration <= 0:
            raise AudioValidationException(
                "Audio duration is zero or missing",
                details={"path": str(path), "duration": duration},
            )

        sample_rate = self._as_int(stream.sample_rate)
        if sample_rate is None or sample_rate <= 0:
            raise AudioValidationException(
                "Invalid or missing sample rate",
                details={"path": str(path), "sample_rate": stream.sample_rate},
            )

        channels = stream.channels
        if channels is None or channels <= 0:
            raise AudioValidationException(
                "Invalid or missing channel count",
                details={"path": str(path), "channels": channels},
            )

        logger.info(
            "validation_complete",
            path=str(path),
            codec=codec,
            duration=duration,
            sample_rate=sample_rate,
            channels=channels,
            status="ok",
        )

    def validate_normalized_output(self, path: Path) -> None:
        if not path.exists() or path.stat().st_size == 0:
            raise AudioValidationException(
                "Normalized output is empty or missing",
                details={"path": str(path)},
            )

    @staticmethod
    def _as_float(value: str | float | int | None) -> float | None:
        if value is None or value == "N/A":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_int(value: str | float | int | None) -> int | None:
        if value is None or value == "N/A":
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
