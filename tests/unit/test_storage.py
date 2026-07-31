"""Unit tests for StorageProvider interface contract."""

import pytest

from app.config.settings import R2Settings
from app.infrastructure.r2.client import CloudflareR2Storage


@pytest.mark.asyncio
async def test_r2_health_check_requires_credentials() -> None:
    storage = CloudflareR2Storage(R2Settings())
    assert await storage.health_check() is False


@pytest.mark.asyncio
async def test_r2_upload_is_deferred() -> None:
    storage = CloudflareR2Storage(
        R2Settings(
            account_id="acct",
            access_key_id="key",
            secret_access_key="test-secret",  # noqa: S106
            bucket_name="bucket",
        )
    )
    with pytest.raises(NotImplementedError):
        await storage.upload("key", b"data")
