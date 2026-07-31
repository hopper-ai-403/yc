"""Corrupted / invalid codec preprocessing edge cases."""

from pathlib import Path

import pytest

from app.audio.preprocessing.exceptions import AudioValidationException
from app.audio.preprocessing.metadata import ProbeResult, ProbeStream
from app.audio.preprocessing.validator import AudioValidator
from app.config.settings import PreprocessingSettings


def test_corrupted_probe_missing_sample_rate() -> None:
    validator = AudioValidator(PreprocessingSettings())
    probe = ProbeResult(
        streams=[
            ProbeStream(
                codec_type="audio",
                codec_name="mp3",
                sample_rate=None,
                channels=1,
                duration="1.0",
            )
        ]
    )
    with pytest.raises(AudioValidationException, match="sample rate"):
        validator.validate_probe(probe, path=Path("corrupt.mp3"))


def test_normalized_output_empty_rejected(tmp_path: Path) -> None:
    validator = AudioValidator(PreprocessingSettings())
    empty = tmp_path / "out.wav"
    empty.write_bytes(b"")
    with pytest.raises(AudioValidationException, match="empty"):
        validator.validate_normalized_output(empty)
