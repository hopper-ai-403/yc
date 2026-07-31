"""Unit tests for Cloudflare R2 StorageProvider."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.config.settings import R2Settings
from app.infrastructure.r2.client import CloudflareR2Storage
from app.shared.exceptions import StorageException


def _settings() -> R2Settings:
    return R2Settings(
        account_id="acct",
        access_key_id="0" * 32,
        secret_access_key="s" * 64,
        bucket_name="bucket",
        endpoint_url="https://example.r2.cloudflarestorage.com",
    )


@pytest.mark.asyncio
async def test_r2_health_check_requires_credentials() -> None:
    storage = CloudflareR2Storage(
        R2Settings(
            account_id="",
            access_key_id="",
            secret_access_key="",
            bucket_name="",
        )
    )
    assert await storage.health_check() is False


@pytest.mark.asyncio
async def test_r2_upload_and_aliases() -> None:
    mock_client = MagicMock()
    storage = CloudflareR2Storage(_settings())
    storage._client = mock_client

    key = await storage.upload_file(
        "uploads/b/original/a.wav", b"data", content_type="audio/wav"
    )
    assert key == "uploads/b/original/a.wav"
    mock_client.put_object.assert_called_once()

    mock_client.head_object.return_value = {}
    assert await storage.file_exists("uploads/b/original/a.wav") is True

    mock_client.list_objects_v2.return_value = {
        "Contents": [{"Key": "uploads/b/original/a.wav"}]
    }
    keys = await storage.list_files("uploads/b/")
    assert keys == ["uploads/b/original/a.wav"]

    mock_client.generate_presigned_url.return_value = "https://signed.example/a.wav"
    url = await storage.generate_signed_url("uploads/b/original/a.wav")
    assert url.startswith("https://")


@pytest.mark.asyncio
async def test_r2_upload_failure_raises_storage_exception() -> None:
    mock_client = MagicMock()
    mock_client.put_object.side_effect = ClientError(
        {"Error": {"Code": "500", "Message": "boom"}},
        "PutObject",
    )
    storage = CloudflareR2Storage(_settings())
    storage._client = mock_client

    with pytest.raises(StorageException):
        await storage.upload("key", b"data")


@pytest.mark.asyncio
async def test_r2_health_check_with_mocked_head_bucket() -> None:
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client):
        storage = CloudflareR2Storage(_settings())
        assert await storage.health_check() is True
        mock_client.head_bucket.assert_called_once()
