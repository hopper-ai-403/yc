"""Cloudflare R2 StorageProvider implementation.

Upload business logic is deferred. Methods that require live credentials
raise NotImplementedError until Sprint 1 wires real R2 operations.
"""

from typing import BinaryIO

from app.config.settings import R2Settings
from app.shared.exceptions import StorageException
from app.shared.storage.provider import StorageProvider


class CloudflareR2Storage(StorageProvider):
    """Cloudflare R2 implementation of StorageProvider.

    boto3 is imported only inside this infrastructure module.
    """

    def __init__(self, settings: R2Settings) -> None:
        self._settings = settings
        self._client = None

    def _ensure_configured(self) -> None:
        if not self._settings.account_id or not self._settings.access_key_id:
            raise StorageException(
                "R2 credentials are not configured",
                details={"bucket": self._settings.bucket_name},
            )

    def _get_client(self) -> object:
        """Lazy-create the S3-compatible client. Deferred until Sprint 1."""
        self._ensure_configured()
        raise NotImplementedError("R2 client initialization is deferred to Sprint 1")

    async def upload(
        self,
        key: str,
        data: BinaryIO | bytes,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload an object to R2. Deferred to Sprint 1."""
        raise NotImplementedError("R2 upload is deferred to Sprint 1")

    async def download(self, key: str) -> bytes:
        """Download an object from R2. Deferred to Sprint 1."""
        raise NotImplementedError("R2 download is deferred to Sprint 1")

    async def delete(self, key: str) -> None:
        """Delete an object from R2. Deferred to Sprint 1."""
        raise NotImplementedError("R2 delete is deferred to Sprint 1")

    async def exists(self, key: str) -> bool:
        """Check object existence in R2. Deferred to Sprint 1."""
        raise NotImplementedError("R2 exists is deferred to Sprint 1")

    async def list(self, prefix: str = "", *, max_keys: int = 1000) -> list[str]:
        """List objects in R2. Deferred to Sprint 1."""
        raise NotImplementedError("R2 list is deferred to Sprint 1")

    async def generate_signed_url(
        self,
        key: str,
        *,
        expires_in: int = 3600,
        method: str = "GET",
    ) -> str:
        """Generate a signed URL. Deferred to Sprint 1."""
        raise NotImplementedError("R2 signed URL generation is deferred to Sprint 1")

    async def health_check(self) -> bool:
        """Return True when R2 settings appear configured.

        Full connectivity check is deferred until credentials and client
        wiring land in Sprint 1.
        """
        return bool(
            self._settings.account_id
            and self._settings.access_key_id
            and self._settings.secret_access_key
            and self._settings.bucket_name
        )
