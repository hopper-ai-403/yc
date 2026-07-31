"""Unit tests for audio validation and metadata helpers."""

from pathlib import Path

import pytest

from app.audio.preprocessing.exceptions import AudioValidationException
from app.audio.preprocessing.metadata import AudioTechnicalMetadata, ProbeResult, ProbeStream
from app.audio.preprocessing.validator import AudioValidator
from app.config.settings import PreprocessingSettings


def test_reject_zero_byte_files() -> None:
    validator = AudioValidator(PreprocessingSettings())
    with pytest.raises(AudioValidationException, match="Zero-byte"):
        validator.validate_file_bytes(b"", filename="empty.wav")


def test_reject_invalid_header() -> None:
    validator = AudioValidator(PreprocessingSettings())
    with pytest.raises(AudioValidationException, match="header"):
        validator.validate_file_bytes(b"RIFF", filename="tiny.wav")


def test_reject_missing_streams() -> None:
    validator = AudioValidator(PreprocessingSettings())
    with pytest.raises(AudioValidationException, match="Missing audio streams"):
        validator.validate_probe(ProbeResult(streams=[]), path=Path("x.wav"))


def test_reject_unsupported_codec() -> None:
    validator = AudioValidator(PreprocessingSettings())
    probe = ProbeResult(
        streams=[
            ProbeStream(
                codec_type="audio",
                codec_name="cook",
                sample_rate="44100",
                channels=2,
                duration="1.0",
            )
        ]
    )
    with pytest.raises(AudioValidationException, match="Unsupported codec"):
        validator.validate_probe(probe, path=Path("x.ra"))


def test_reject_zero_duration() -> None:
    validator = AudioValidator(PreprocessingSettings())
    probe = ProbeResult(
        streams=[
            ProbeStream(
                codec_type="audio",
                codec_name="mp3",
                sample_rate="44100",
                channels=1,
                duration="0",
            )
        ]
    )
    with pytest.raises(AudioValidationException, match="duration"):
        validator.validate_probe(probe, path=Path("x.mp3"))


def test_accept_wav_mp3_ogg_codecs() -> None:
    validator = AudioValidator(PreprocessingSettings())
    for codec in ("pcm_s16le", "mp3", "vorbis"):
        probe = ProbeResult(
            streams=[
                ProbeStream(
                    codec_type="audio",
                    codec_name=codec,
                    sample_rate="44100",
                    channels=2,
                    duration="1.25",
                )
            ]
        )
        validator.validate_probe(probe, path=Path(f"x.{codec}"))


def test_metadata_schema_roundtrip() -> None:
    meta = AudioTechnicalMetadata(
        duration=1.5,
        sample_rate=44100,
        channels=2,
        bitrate=128000,
        codec="mp3",
        container="mp3",
        file_size=1000,
        peak_db=-1.0,
        rms_db=-18.0,
        normalized_sample_rate=16000,
        normalized_channels=1,
        normalized_codec="pcm_s16le",
        normalized_file_size=48000,
        normalized_duration=1.5,
    )
    restored = AudioTechnicalMetadata.model_validate(meta.to_storage_dict())
    assert restored.normalized_sample_rate == 16000
    assert restored.channels == 2
