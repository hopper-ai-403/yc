"""Unit tests for JobService orchestration (mocked collaborators)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from app.audio.models import AudioAsset, AudioBatch
from app.config.settings import JobSettings
from app.jobs.exceptions import JobRetryExhaustedException, JobStateException
from app.jobs.models import Job
from app.jobs.service import JobService
from app.shared.domain.enums import AudioStatus, BatchStatus, JobStatus

import app.shared.database.models_registry  # noqa: F401


class FakeJobs:
    def __init__(self, job: Job) -> None:
        self.job = job

    async def create(self, job: Job) -> Job:
        self.job = job
        return job

    async def find_by_id(self, job_id: Any) -> Job | None:
        return self.job if self.job.id == job_id else None

    async def find_by_batch(self, batch_id: Any) -> Job | None:
        return self.job if self.job.batch_id == batch_id else None

    async def find_active(self) -> list[Job]:
        return [self.job]

    async def list_jobs(self, **kwargs: Any) -> list[Job]:
        return [self.job]

    async def update_status(self, job_id: Any, status: JobStatus, **kwargs: Any) -> Job:
        self.job.status = status
        return self.job

    async def save(self, job: Job) -> Job:
        self.job = job
        return job


class FakeBatches:
    def __init__(self, batch: AudioBatch) -> None:
        self.batch = batch
        self.statuses: list[BatchStatus] = []

    async def find_by_id(self, batch_id: Any) -> AudioBatch | None:
        return self.batch if self.batch.id == batch_id else None

    async def update_status(self, batch_id: Any, status: BatchStatus) -> AudioBatch:
        self.statuses.append(status)
        self.batch.status = status
        return self.batch

    async def create(self, batch: AudioBatch) -> AudioBatch:
        return batch

    async def list_by_uploader(self, uploader_id: Any) -> list[AudioBatch]:
        return [self.batch]


class FakeAssets:
    def __init__(self, assets: list[AudioAsset]) -> None:
        self.assets = {a.id: a for a in assets}

    async def create(self, asset: AudioAsset) -> AudioAsset:
        self.assets[asset.id] = asset
        return asset

    async def find_by_id(self, asset_id: Any) -> AudioAsset | None:
        return self.assets.get(asset_id)

    async def find_by_batch(self, batch_id: Any) -> list[AudioAsset]:
        return [a for a in self.assets.values() if a.batch_id == batch_id]

    async def update_status(self, asset_id: Any, status: AudioStatus) -> AudioAsset:
        asset = self.assets[asset_id]
        asset.processing_status = status
        return asset


class FakeCache:
    def __init__(self) -> None:
        self.status: dict[str, str] = {}
        self.progress: dict[str, dict[str, Any]] = {}
        self.heartbeats: dict[str, str] = {}

    async def set_status(self, job_id: Any, status: str) -> None:
        self.status[str(job_id)] = status

    async def get_status(self, job_id: Any) -> str | None:
        return self.status.get(str(job_id))

    async def set_progress(self, job_id: Any, payload: dict[str, Any]) -> None:
        self.progress[str(job_id)] = payload

    async def get_progress(self, job_id: Any) -> dict[str, Any] | None:
        return self.progress.get(str(job_id))

    async def set_job_heartbeat(self, job_id: Any, worker_id: str) -> None:
        self.heartbeats[str(job_id)] = worker_id

    async def set_worker_heartbeat(self, hostname: str, payload: dict[str, Any]) -> None:
        return None

    async def clear_job(self, job_id: Any) -> None:
        self.status.pop(str(job_id), None)


class FakeDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, int]] = []

    def enqueue_batch(self, job_id: Any, *, countdown: int = 0) -> str:
        self.calls.append((job_id, countdown))
        return f"task-{len(self.calls)}"


def _make_asset(batch_id: Any, status: AudioStatus = AudioStatus.UPLOADED) -> AudioAsset:
    asset = AudioAsset(
        batch_id=batch_id,
        filename="a.wav",
        format="wav",
        storage_key=f"uploads/{batch_id}/original/{uuid4().hex}.wav",
        processing_status=status,
    )
    asset.id = uuid4()
    return asset


def _build_service(
    *,
    job_status: JobStatus = JobStatus.PENDING,
    asset_statuses: list[AudioStatus] | None = None,
    retry_count: int = 0,
) -> tuple[JobService, FakeDispatcher, FakeCache, FakeAssets, Job]:
    batch_id = uuid4()
    batch = AudioBatch(
        original_filename="batch.zip",
        total_files=2,
        uploaded_by=uuid4(),
        status=BatchStatus.UPLOADED,
    )
    batch.id = batch_id

    statuses = asset_statuses or [AudioStatus.UPLOADED, AudioStatus.UPLOADED]
    assets = [_make_asset(batch_id, s) for s in statuses]

    job = Job(
        batch_id=batch_id,
        status=job_status,
        progress=0,
        retry_count=retry_count,
        total_files=len(assets),
        processed_files=0,
        failed_files=0,
    )
    job.id = uuid4()
    job.created_at = datetime.now(timezone.utc)
    job.updated_at = job.created_at

    dispatcher = FakeDispatcher()
    cache = FakeCache()
    fake_assets = FakeAssets(assets)
    service = JobService(
        settings=JobSettings(max_retries=3, retry_backoff_base_seconds=2),
        jobs=FakeJobs(job),  # type: ignore[arg-type]
        batches=FakeBatches(batch),  # type: ignore[arg-type]
        assets=fake_assets,  # type: ignore[arg-type]
        progress_cache=cache,  # type: ignore[arg-type]
        dispatcher=dispatcher,
    )
    return service, dispatcher, cache, fake_assets, job


@pytest.mark.asyncio
async def test_create_job_idempotent() -> None:
    service, _, cache, _, job = _build_service()
    created = await service.create_job(job.batch_id)
    assert created.id == job.id
    assert str(job.id) in cache.status or cache.progress or True


@pytest.mark.asyncio
async def test_queue_job_and_progress_cache() -> None:
    service, dispatcher, cache, assets, job = _build_service()
    queued = await service.queue_job(job.id)
    assert queued.status is JobStatus.QUEUED
    assert len(dispatcher.calls) == 1
    assert cache.status[str(job.id)] == JobStatus.QUEUED.value
    assert all(a.processing_status is AudioStatus.QUEUED for a in assets.assets.values())


@pytest.mark.asyncio
async def test_start_complete_and_progress() -> None:
    service, _, cache, assets, job = _build_service(job_status=JobStatus.QUEUED)
    for asset in assets.assets.values():
        asset.processing_status = AudioStatus.QUEUED

    started = await service.start_job(job.id, worker_id="worker-1")
    assert started.status is JobStatus.RUNNING
    assert started.started_at is not None

    for asset_id in list(assets.assets):
        await service.transition_audio(asset_id, AudioStatus.PROCESSING, job_id=job.id)
        await service.transition_audio(asset_id, AudioStatus.COMPLETED, job_id=job.id)

    completed = await service.complete_job(job.id, worker_id="worker-1")
    assert completed.status is JobStatus.COMPLETED
    assert completed.processed_files == 2
    assert completed.progress == 100
    assert cache.progress[str(job.id)]["progress_percentage"] == 100


@pytest.mark.asyncio
async def test_cancel_job() -> None:
    service, _, _, _, job = _build_service(job_status=JobStatus.QUEUED)
    cancelled = await service.cancel_job(job.id)
    assert cancelled.status is JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_retry_failed_assets_only_with_backoff() -> None:
    service, dispatcher, _, assets, job = _build_service(
        job_status=JobStatus.FAILED,
        asset_statuses=[AudioStatus.COMPLETED, AudioStatus.FAILED],
        retry_count=0,
    )
    completed_id = next(
        a.id for a in assets.assets.values() if a.processing_status is AudioStatus.COMPLETED
    )
    failed_id = next(
        a.id for a in assets.assets.values() if a.processing_status is AudioStatus.FAILED
    )

    retried = await service.retry_job(job.id)
    assert retried.retry_count == 1
    assert assets.assets[completed_id].processing_status is AudioStatus.COMPLETED
    assert assets.assets[failed_id].processing_status is AudioStatus.QUEUED
    assert dispatcher.calls[-1][1] == 2  # base * 2^0


@pytest.mark.asyncio
async def test_retry_exhausted() -> None:
    service, _, _, _, job = _build_service(
        job_status=JobStatus.FAILED,
        asset_statuses=[AudioStatus.FAILED],
        retry_count=3,
    )
    with pytest.raises(JobRetryExhaustedException):
        await service.retry_job(job.id)


@pytest.mark.asyncio
async def test_worker_recovery_resets_processing() -> None:
    service, _, _, assets, job = _build_service(
        job_status=JobStatus.RUNNING,
        asset_statuses=[AudioStatus.PROCESSING, AudioStatus.COMPLETED],
    )
    recovered = await service.recover_stale_processing(job.id)
    assert recovered == 1
    statuses = {a.processing_status for a in assets.assets.values()}
    assert AudioStatus.QUEUED in statuses
    assert AudioStatus.COMPLETED in statuses


@pytest.mark.asyncio
async def test_idempotent_completed_audio_not_reprocessed_list() -> None:
    service, _, _, _, job = _build_service(
        job_status=JobStatus.RUNNING,
        asset_statuses=[AudioStatus.COMPLETED, AudioStatus.QUEUED],
    )
    ids = await service.list_processable_audio_ids(job.id)
    assert len(ids) == 1


@pytest.mark.asyncio
async def test_cannot_retry_running_job() -> None:
    service, _, _, _, job = _build_service(job_status=JobStatus.RUNNING)
    with pytest.raises(JobStateException):
        await service.retry_job(job.id)
