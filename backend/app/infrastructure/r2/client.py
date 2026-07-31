"""Cloudflare R2 StorageProvider implementation using the S3-compatible API."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any, BinaryIO, cast

from botocore.exceptions import BotoCoreError, ClientError

from app.config.settings import R2Settings
from app.shared.exceptions import StorageException
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)


class CloudflareR2Storage(StorageProvider):
    """Cloudflare R2 implementation of StorageProvider.

    boto3 is imported only inside this infrastructure module.
    """

    def __init__(self, settings: R2Settings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _ensure_configured(self) -> None:
        if not (
            self._settings.account_id
            and self._settings.access_key_id
            and self._settings.secret_access_key
            and self._settings.bucket_name
        ):
            raise StorageException(
                "R2 credentials are not configured",
                details={"bucket": self._settings.bucket_name},
            )

    def _endpoint(self) -> str:
        if self._settings.endpoint_url:
            return self._settings.endpoint_url
        return f"https://{self._settings.account_id}.r2.cloudflarestorage.com"

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        self._ensure_configured()
        import boto3

        self._client = boto3.client(
            "s3",
            endpoint_url=self._endpoint(),
            aws_access_key_id=self._settings.access_key_id,
            aws_secret_access_key=self._settings.secret_access_key,
            region_name=self._settings.region or "auto",
        )
        return self._client

    async def _run(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(partial(func, *args, **kwargs))

    def _read_bytes(self, data: BinaryIO | bytes) -> bytes:
        if isinstance(data, bytes):
            return data
        payload = data.read()
        if isinstance(payload, str):
            return payload.encode("utf-8")
        return cast(bytes, payload)

    async def upload(
        self,
        key: str,
        data: BinaryIO | bytes,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        client = self._get_client()
        body = self._read_bytes(data)
        extra: dict[str, Any] = {}
        if content_type:
            extra["ContentType"] = content_type
        if metadata:
            extra["Metadata"] = metadata
        try:
            await self._run(
                client.put_object,
                Bucket=self._settings.bucket_name,
                Key=key,
                Body=body,
                **extra,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("r2_upload_failed", key=key)
            raise StorageException(
                "Failed to upload object to R2",
                details={"key": key, "error": str(exc)},
            ) from exc
        return key

    async def download(self, key: str) -> bytes:
        client = self._get_client()
        try:
            response = await self._run(
                client.get_object,
                Bucket=self._settings.bucket_name,
                Key=key,
            )
            body = response["Body"].read()
            return cast(bytes, body)
        except (BotoCoreError, ClientError) as exc:
            logger.exception("r2_download_failed", key=key)
            raise StorageException(
                "Failed to download object from R2",
                details={"key": key, "error": str(exc)},
            ) from exc

    async def delete(self, key: str) -> None:
        client = self._get_client()
        try:
            await self._run(
                client.delete_object,
                Bucket=self._settings.bucket_name,
                Key=key,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("r2_delete_failed", key=key)
            raise StorageException(
                "Failed to delete object from R2",
                details={"key": key, "error": str(exc)},
            ) from exc

    async def exists(self, key: str) -> bool:
        client = self._get_client()
        try:
            await self._run(
                client.head_object,
                Bucket=self._settings.bucket_name,
                Key=key,
            )
            return True
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise StorageException(
                "Failed to check object existence in R2",
                details={"key": key, "error": str(exc)},
            ) from exc
        except BotoCoreError as exc:
            raise StorageException(
                "Failed to check object existence in R2",
                details={"key": key, "error": str(exc)},
            ) from exc

    async def list(self, prefix: str = "", *, max_keys: int = 1000) -> list[str]:
        client = self._get_client()
        try:
            response = await self._run(
                client.list_objects_v2,
                Bucket=self._settings.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageException(
                "Failed to list objects in R2",
                details={"prefix": prefix, "error": str(exc)},
            ) from exc
        contents = response.get("Contents") or []
        return [str(item["Key"]) for item in contents if "Key" in item]

    async def generate_signed_url(
        self,
        key: str,
        *,
        expires_in: int = 3600,
        method: str = "GET",
    ) -> str:
        client = self._get_client()
        client_method = "get_object" if method.upper() == "GET" else "put_object"
        try:
            url = await self._run(
                client.generate_presigned_url,
                ClientMethod=client_method,
                Params={
                    "Bucket": self._settings.bucket_name,
                    "Key": key,
                },
                ExpiresIn=expires_in,
            )
            return str(url)
        except (BotoCoreError, ClientError) as exc:
            raise StorageException(
                "Failed to generate signed URL",
                details={"key": key, "error": str(exc)},
            ) from exc

    async def health_check(self) -> bool:
        if not (
            self._settings.account_id
            and self._settings.access_key_id
            and self._settings.secret_access_key
            and self._settings.bucket_name
        ):
            return False
        try:
            client = self._get_client()
            await self._run(
                client.head_bucket,
                Bucket=self._settings.bucket_name,
            )
            return True
        except Exception:
            logger.warning("r2_health_check_failed", bucket=self._settings.bucket_name)
            return False
