"""Evaluation repository: persistence contract for BatchMetrics."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.models import BatchMetrics


class BatchMetricsRepository(ABC):
    """Persistence contract for BatchMetrics entities."""

    @abstractmethod
    async def find_by_batch(self, batch_id: UUID) -> BatchMetrics | None:
        """Find metrics for a batch."""

    @abstractmethod
    async def upsert(
        self,
        batch_id: UUID,
        *,
        total_audio: int,
        successful_predictions: int,
        failed_predictions: int,
        success_rate: float,
        average_processing_time_ms: float | None,
        min_processing_time_ms: float | None,
        max_processing_time_ms: float | None,
        average_confidence: float | None,
        batch_duration_ms: float | None,
        computed_at: datetime,
    ) -> BatchMetrics:
        """Insert or refresh metrics for a batch (idempotent)."""


class SqlAlchemyBatchMetricsRepository(BatchMetricsRepository):
    """SQLAlchemy-backed BatchMetricsRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_batch(self, batch_id: UUID) -> BatchMetrics | None:
        statement = select(BatchMetrics).where(BatchMetrics.batch_id == batch_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        batch_id: UUID,
        *,
        total_audio: int,
        successful_predictions: int,
        failed_predictions: int,
        success_rate: float,
        average_processing_time_ms: float | None,
        min_processing_time_ms: float | None,
        max_processing_time_ms: float | None,
        average_confidence: float | None,
        batch_duration_ms: float | None,
        computed_at: datetime,
    ) -> BatchMetrics:
        metrics = await self.find_by_batch(batch_id)
        if metrics is None:
            metrics = BatchMetrics(batch_id=batch_id, computed_at=computed_at)
            self._session.add(metrics)
        metrics.total_audio = total_audio
        metrics.successful_predictions = successful_predictions
        metrics.failed_predictions = failed_predictions
        metrics.success_rate = success_rate
        metrics.average_processing_time_ms = average_processing_time_ms
        metrics.min_processing_time_ms = min_processing_time_ms
        metrics.max_processing_time_ms = max_processing_time_ms
        metrics.average_confidence = average_confidence
        metrics.batch_duration_ms = batch_duration_ms
        metrics.computed_at = computed_at
        await self._session.flush()
        await self._session.refresh(metrics)
        return metrics
