"""StorageProvider interface for object storage backends."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import BinaryIO


class StorageProvider(ABC):
    """Abstract interface for object storage operations."""

    @abstractmethod
    async def upload(
        self,
        key: str,
        data: BinaryIO | bytes,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Upload an object and return its storage key."""

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download an object by key."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete an object by key."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if the object exists."""

    @abstractmethod
    async def list(self, prefix: str = "", *, max_keys: int = 1000) -> list[str]:
        """List object keys under an optional prefix."""

    @abstractmethod
    async def generate_signed_url(
        self,
        key: str,
        *,
        expires_in: int = 3600,
        method: str = "GET",
    ) -> str:
        """Generate a time-limited signed URL for the object."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if storage is reachable."""

    async def stream_download(self, key: str) -> AsyncIterator[bytes]:
        """Optionally stream download; default loads full object."""
        data = await self.download(key)
        yield data
