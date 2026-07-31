"""Upload validation and ZIP extraction unit tests."""

import io
import zipfile

import pytest

from app.config.settings import UploadSettings
from app.upload.exceptions import (
    CorruptedArchiveException,
    DuplicateFilenameException,
    UnsupportedFormatException,
    UploadValidationException,
)
from app.upload.schemas import ValidatedAudioFile
from app.upload.validation import ensure_unique_filenames, validate_audio_bytes
from app.upload.zip_extractor import extract_audio_from_zip


@pytest.fixture
def upload_settings() -> UploadSettings:
    return UploadSettings()


def test_validate_audio_bytes_accepts_wav(upload_settings: UploadSettings) -> None:
    result = validate_audio_bytes(
        filename="call.wav",
        content=b"RIFF....WAVE",
        declared_mime="audio/wav",
        settings=upload_settings,
    )
    assert result.extension == "wav"
    assert result.checksum_sha256
    assert result.size_bytes > 0


def test_validate_audio_bytes_rejects_unsupported(
    upload_settings: UploadSettings,
) -> None:
    with pytest.raises(UnsupportedFormatException):
        validate_audio_bytes(
            filename="notes.txt",
            content=b"hello",
            declared_mime="text/plain",
            settings=upload_settings,
        )


def test_validate_audio_bytes_rejects_oversized(
    upload_settings: UploadSettings,
) -> None:
    settings = UploadSettings(max_file_size_bytes=4)
    with pytest.raises(UploadValidationException):
        validate_audio_bytes(
            filename="big.wav",
            content=b"12345",
            declared_mime="audio/wav",
            settings=settings,
        )


def test_duplicate_filenames_rejected() -> None:
    files = [
        ValidatedAudioFile(
            filename="a.wav",
            extension="wav",
            mime_type="audio/wav",
            size_bytes=1,
            checksum_sha256="a" * 64,
            content=b"1",
        ),
        ValidatedAudioFile(
            filename="A.WAV",
            extension="wav",
            mime_type="audio/wav",
            size_bytes=1,
            checksum_sha256="b" * 64,
            content=b"2",
        ),
    ]
    with pytest.raises(DuplicateFilenameException):
        ensure_unique_filenames(files)


def test_extract_audio_from_zip(upload_settings: UploadSettings) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.wav", b"RIFFWAVDATA")
        archive.writestr("readme.txt", b"ignore me")
        archive.writestr("__MACOSX/._a.wav", b"meta")
    accepted, rejected = extract_audio_from_zip(
        filename="batch.zip",
        content=buffer.getvalue(),
        settings=upload_settings,
    )
    assert len(accepted) == 1
    assert accepted[0].filename == "a.wav"
    assert any(item["reason"] == "unsupported_format" for item in rejected)


def test_corrupted_zip_rejected(upload_settings: UploadSettings) -> None:
    with pytest.raises(CorruptedArchiveException):
        extract_audio_from_zip(
            filename="bad.zip",
            content=b"not-a-zip",
            settings=upload_settings,
        )
