"""Batch export artifacts: CSV/JSON generation and R2 upload.

Exports include only successfully predicted files. Generation is idempotent:
existing R2 artifacts are reused unless regeneration is requested.
"""

from __future__ import annotations

import json
from uuid import UUID

from app.evaluation.exceptions import ExportNotFoundException
from app.prediction.export import PredictionExportService
from app.shared.logging.setup import get_logger
from app.shared.storage.provider import StorageProvider

logger = get_logger(__name__)

CSV_EXPORT_NAME = "results.csv"
JSON_EXPORT_NAME = "results.json"


def exports_csv_key(batch_id: UUID) -> str:
    return f"uploads/{batch_id}/exports/{CSV_EXPORT_NAME}"


def exports_json_key(batch_id: UUID) -> str:
    return f"uploads/{batch_id}/exports/{JSON_EXPORT_NAME}"


class BatchExporter:
    """Generate batch exports and manage their R2 artifacts."""

    def __init__(
        self,
        *,
        storage: StorageProvider,
        predictions_export: PredictionExportService,
        signed_url_expiry_seconds: int = 3600,
    ) -> None:
        self._storage = storage
        self._export = predictions_export
        self._expiry = signed_url_expiry_seconds

    async def generate_and_upload(
        self,
        batch_id: UUID,
        *,
        regenerate: bool = False,
    ) -> tuple[str, str]:
        """Generate CSV + JSON and upload to uploads/{batch_id}/exports/."""
        csv_key = exports_csv_key(batch_id)
        json_key = exports_json_key(batch_id)

        if not regenerate and await self._exists(csv_key) and await self._exists(json_key):
            logger.info(
                "batch_exports_skipped_idempotent",
                batch_id=str(batch_id),
                csv_key=csv_key,
                json_key=json_key,
            )
            return csv_key, json_key

        csv_text = await self._export.export_csv(batch_id)
        json_payload = await self._export.export_json(batch_id)

        await self._storage.upload(
            csv_key,
            csv_text.encode("utf-8"),
            content_type="text/csv",
            metadata={"batch_id": str(batch_id), "stage": "export", "format": "csv"},
        )
        await self._storage.upload(
            json_key,
            json.dumps(json_payload).encode("utf-8"),
            content_type="application/json",
            metadata={"batch_id": str(batch_id), "stage": "export", "format": "json"},
        )
        logger.info(
            "batch_exports_uploaded",
            batch_id=str(batch_id),
            csv_key=csv_key,
            json_key=json_key,
            row_count=len(json_payload),
            status="ok",
        )
        return csv_key, json_key

    async def get_signed_exports(self, batch_id: UUID) -> list[dict[str, str | int]]:
        """Return signed URLs for existing export artifacts."""
        items: list[dict[str, str | int]] = []
        for name, key in (
            (CSV_EXPORT_NAME, exports_csv_key(batch_id)),
            (JSON_EXPORT_NAME, exports_json_key(batch_id)),
        ):
            if not await self._exists(key):
                continue
            items.append(
                {
                    "name": name,
                    "storage_key": key,
                    "url": await self._storage.get_signed_url(
                        key,
                        expires_in=self._expiry,
                    ),
                    "expires_in": self._expiry,
                }
            )
        if not items:
            raise ExportNotFoundException(batch_id)
        return items

    async def _exists(self, key: str) -> bool:
        try:
            await self._storage.download(key)
        except Exception:
            return False
        return True
