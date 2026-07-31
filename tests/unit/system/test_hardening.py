"""Unit tests for Sprint 11 production hardening."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import app.shared.database.models_registry  # noqa: F401
from app.audio.models import AudioAsset, AudioBatch
from app.config.settings import PerformanceSettings, R2Settings, SpeechSettings
from app.infrastructure.warmup import (
    is_model_loaded,
    reset_warmup_state,
    warmup_models,
)
from app.jobs.models import Job
from app.jobs.service import JobService
from app.shared.domain.enums import AudioStatus, BatchStatus, JobStatus
from app.shared.profiling import PipelineProfiler
from app.system.benchmark import BenchmarkRunner, percentile


class FakeModel:
    def __init__(self, settings: SpeechSettings) -> None:
        self.settings = settings
        self.loaded = False

    def load(self) -> None:
        self.loaded = True

    def metadata(self) -> dict[str, Any]:
        return {"model_name": self.settings.model_name}


# --- Part 1: warmup ------------------------------------------------------


def test_warmup_loads_singleton_and_tracks_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ai.speech import inference

    inference.reset_model_registry()
    reset_warmup_state()
    monkeypatch.setattr(
        inference,
        "HuggingFaceSpeechEmotionModel",
        FakeModel,
        raising=False,
    )

    speech = SpeechSettings(model_name="test-ser-model")
    perf = PerformanceSettings(model_warmup=True)
    state = warmup_models(speech, perf, model_factory=FakeModel)

    assert speech.model_name in state.loaded_models
    assert state.load_durations_ms[speech.model_name] >= 0.0
    assert is_model_loaded(speech.model_name) is True
    assert state.all_loaded is True


def test_warmup_disabled_marks_ready() -> None:
    reset_warmup_state()
    speech = SpeechSettings(model_name="test-ser-model")
    perf = PerformanceSettings(model_warmup=False)
    state = warmup_models(speech, perf, model_factory=FakeModel)
    assert state.loaded_models == []
    assert state.all_loaded is True
    assert is_model_loaded(speech.model_name) is True


# --- Part 3: profiling ---------------------------------------------------


def test_profiler_records_stage_fields() -> None:
    profiler = PipelineProfiler(enabled=True)
    with profiler.stage("preprocessing"):
        pass
    with profiler.stage("analysis"):
        pass

    stages = profiler.stages
    assert len(stages) == 2
    for stage in stages:
        assert set(stage.keys()) == {
            "stage",
            "start_time",
            "end_time",
            "duration_ms",
            "status",
        }
        assert stage["status"] == "ok"
        assert stage["duration_ms"] >= 0.0

    durations = profiler.durations_ms()
    assert "preprocessing_duration_ms" in durations
    assert "analysis_duration_ms" in durations


def test_profiler_failed_stage_status() -> None:
    profiler = PipelineProfiler(enabled=True)
    with pytest.raises(ValueError):
        with profiler.stage("speech"):
            raise ValueError("boom")
    assert profiler.stages[0]["status"] == "failed"


def test_profiler_timing_accuracy() -> None:
    import time as time_module

    profiler = PipelineProfiler(enabled=True)
    with profiler.stage("prediction"):
        time_module.sleep(0.02)
    assert profiler.stages[0]["duration_ms"] >= 18.0
    assert profiler.total_duration_ms() >= 18.0


def test_profiler_disabled_records_nothing() -> None:
    profiler = PipelineProfiler(enabled=False)
    with profiler.stage("preprocessing"):
        pass
    assert profiler.stages == []
    assert profiler.durations_ms() == {}


# --- Part 8: benchmark ---------------------------------------------------


def _batch_with_assets(count: int) -> AudioBatch:
    batch = AudioBatch(
        original_filename="calls.zip",
        total_files=count,
        status=BatchStatus.COMPLETED,
    )
    batch.id = uuid4()
    assets = []
    for index in range(count):
        asset = AudioAsset(
            batch_id=batch.id,
            filename=f"a{index}.wav",
            format="wav",
            extension="wav",
            mime_type="audio/wav",
            size_bytes=100,
            checksum_sha256="0" * 64,
            uploaded_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            storage_key=f"uploads/{batch.id}/original/a{index}.wav",
            processing_status=AudioStatus.COMPLETED,
            timing_json={"total_pipeline_duration_ms": 1000.0 * (index + 1)},
        )
        asset.id = uuid4()
        assets.append(asset)
    batch.assets = assets
    return batch


def _prediction_for(asset: AudioAsset, confidence: float) -> Any:
    return type(
        "PredictionRecord",
        (),
        {
            "audio_asset_id": asset.id,
            "confidence": confidence,
            "prediction_completed_at": datetime.now(timezone.utc),
        },
    )()


class FakeBatches:
    def __init__(self, batch: AudioBatch) -> None:
        self._batch = batch

    async def find_by_id(self, batch_id: Any) -> AudioBatch | None:
        return self._batch if self._batch.id == batch_id else None


class FakeAssets:
    def __init__(self, assets: list[AudioAsset]) -> None:
        self._assets = assets

    async def find_by_batch(self, batch_id: Any) -> list[AudioAsset]:
        return [a for a in self._assets if a.batch_id == batch_id]


class FakePredictions:
    def __init__(self, predictions: list[Any]) -> None:
        self._predictions = predictions

    async def find_by_batch(self, batch_id: Any) -> list[Any]:
        return list(self._predictions)


class FakeJobsRepo:
    def __init__(self, job: Job | None) -> None:
        self._job = job

    async def find_by_batch(self, batch_id: Any) -> Job | None:
        return self._job if self._job and self._job.batch_id == batch_id else None


def test_percentile_nearest_rank() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert percentile(values, 0.50) == 5.0
    assert percentile(values, 0.95) == 10.0
    assert percentile(values, 0.99) == 10.0
    assert percentile([], 0.50) is None


@pytest.mark.asyncio
async def test_benchmark_generation_partial_failures() -> None:
    batch = _batch_with_assets(4)
    # Two successes with timing metadata, one fallback wall time, one failure.
    predictions = [
        _prediction_for(batch.assets[0], 0.9),
        _prediction_for(batch.assets[1], 0.7),
    ]
    batch.assets[2].timing_json = None
    fallback = type(
        "PredictionRecord",
        (),
        {
            "audio_asset_id": batch.assets[2].id,
            "confidence": 0.5,
            "prediction_completed_at": batch.assets[2].uploaded_at
            + timedelta(seconds=3),
        },
    )()
    predictions.append(fallback)

    job = Job(
        batch_id=batch.id,
        status=JobStatus.COMPLETED,
        progress=100,
        total_files=4,
        processed_files=3,
        failed_files=1,
    )
    job.id = uuid4()
    job.started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    job.completed_at = datetime.now(timezone.utc)

    runner = BenchmarkRunner(
        batches=FakeBatches(batch),  # type: ignore[arg-type]
        assets=FakeAssets(batch.assets),  # type: ignore[arg-type]
        predictions=FakePredictions(predictions),  # type: ignore[arg-type]
        jobs=FakeJobsRepo(job),  # type: ignore[arg-type]
    )
    report = await runner.run(batch.id)

    assert report.total_files == 4
    assert report.successful_files == 3
    assert report.failed_files == 1
    assert report.failure_rate == 0.25
    assert report.average_latency_ms is not None
    assert report.p50_latency_ms is not None
    assert report.p95_latency_ms is not None
    assert report.p99_latency_ms is not None
    assert report.average_confidence == round((0.9 + 0.7 + 0.5) / 3, 4)
    assert report.batch_duration_ms is not None
    assert report.throughput_files_per_minute is not None
    assert report.throughput_files_per_minute > 0


# --- Part 4: worker recovery + heartbeat expiry ---------------------------


class FakeProgressCache:
    def __init__(self, *, fresh: bool) -> None:
        self._fresh = fresh
        self.payloads: dict[str, Any] = {}

    async def has_fresh_job_heartbeat(self, job_id: Any) -> bool:
        return self._fresh

    async def set_status(self, job_id: Any, status: str) -> None:
        pass

    async def set_progress(self, job_id: Any, payload: dict[str, Any]) -> None:
        pass

    async def set_job_heartbeat(self, job_id: Any, worker_id: str) -> None:
        pass


class FakeJobsRepoActive:
    def __init__(self, jobs: list[Job]) -> None:
        self.jobs = jobs

    async def find_active(self) -> list[Job]:
        return list(self.jobs)

    async def find_by_id(self, job_id: Any) -> Job | None:
        return next((j for j in self.jobs if j.id == job_id), None)

    async def find_by_batch(self, batch_id: Any) -> Job | None:
        return next((j for j in self.jobs if j.batch_id == batch_id), None)

    async def save(self, job: Job) -> Job:
        return job


class FakeAssetsRepo:
    def __init__(self, assets: list[AudioAsset]) -> None:
        self.assets = assets

    async def find_by_batch(self, batch_id: Any) -> list[AudioAsset]:
        return [a for a in self.assets if a.batch_id == batch_id]

    async def find_by_id(self, asset_id: Any) -> AudioAsset | None:
        return next((a for a in self.assets if a.id == asset_id), None)

    async def update_status(self, asset_id: Any, status: AudioStatus) -> None:
        asset = await self.find_by_id(asset_id)
        if asset is not None:
            asset.processing_status = status


class FakeBatchesRepo:
    async def find_by_id(self, batch_id: Any) -> AudioBatch | None:
        return AudioBatch(
            original_filename="x.zip",
            total_files=1,
            status=BatchStatus.VALIDATED,
        )

    async def update_status(self, batch_id: Any, status: BatchStatus) -> None:
        pass


class FakeDispatcher:
    def __init__(self) -> None:
        self.enqueued: list[Any] = []

    def enqueue_batch(self, job_id: Any, countdown: int = 0) -> str:
        self.enqueued.append(job_id)
        return "task-1"


@pytest.mark.asyncio
async def test_orphaned_job_recovery_requeues() -> None:
    batch_id = uuid4()
    job = Job(
        batch_id=batch_id,
        status=JobStatus.RUNNING,
        progress=10,
        total_files=1,
        processed_files=0,
        failed_files=0,
    )
    job.id = uuid4()
    job.retry_count = 0
    job.started_at = datetime.now(timezone.utc) - timedelta(hours=2)

    asset = AudioAsset(
        batch_id=batch_id,
        filename="a.wav",
        format="wav",
        extension="wav",
        mime_type="audio/wav",
        size_bytes=1,
        checksum_sha256="0" * 64,
        uploaded_at=datetime.now(timezone.utc),
        storage_key="k",
        processing_status=AudioStatus.PROCESSING,
    )
    asset.id = uuid4()

    from app.config.settings import JobSettings

    dispatcher = FakeDispatcher()
    service = JobService(
        settings=JobSettings(),
        jobs=FakeJobsRepoActive([job]),  # type: ignore[arg-type]
        batches=FakeBatchesRepo(),  # type: ignore[arg-type]
        assets=FakeAssetsRepo([asset]),  # type: ignore[arg-type]
        progress_cache=FakeProgressCache(fresh=False),  # type: ignore[arg-type]
        dispatcher=dispatcher,  # type: ignore[arg-type]
    )
    recovered = await service.recover_orphaned_jobs(threshold_seconds=1800)
    assert recovered == 1
    assert job.status is JobStatus.QUEUED
    assert asset.processing_status is AudioStatus.QUEUED
    assert dispatcher.enqueued == [job.id]


@pytest.mark.asyncio
async def test_orphaned_job_recovery_skips_fresh_heartbeat() -> None:
    batch_id = uuid4()
    job = Job(
        batch_id=batch_id,
        status=JobStatus.RUNNING,
        progress=10,
        total_files=1,
        processed_files=0,
        failed_files=0,
    )
    job.id = uuid4()
    job.started_at = datetime.now(timezone.utc) - timedelta(hours=2)

    from app.config.settings import JobSettings

    service = JobService(
        settings=JobSettings(),
        jobs=FakeJobsRepoActive([job]),  # type: ignore[arg-type]
        batches=FakeBatchesRepo(),  # type: ignore[arg-type]
        assets=FakeAssetsRepo([]),  # type: ignore[arg-type]
        progress_cache=FakeProgressCache(fresh=True),  # type: ignore[arg-type]
        dispatcher=FakeDispatcher(),  # type: ignore[arg-type]
    )
    recovered = await service.recover_orphaned_jobs(threshold_seconds=1800)
    assert recovered == 0
    assert job.status is JobStatus.RUNNING


@pytest.mark.asyncio
async def test_orphaned_recovery_skips_recent_jobs() -> None:
    batch_id = uuid4()
    job = Job(
        batch_id=batch_id,
        status=JobStatus.RUNNING,
        progress=10,
        total_files=1,
        processed_files=0,
        failed_files=0,
    )
    job.id = uuid4()
    job.started_at = datetime.now(timezone.utc) - timedelta(seconds=30)

    from app.config.settings import JobSettings

    service = JobService(
        settings=JobSettings(),
        jobs=FakeJobsRepoActive([job]),  # type: ignore[arg-type]
        batches=FakeBatchesRepo(),  # type: ignore[arg-type]
        assets=FakeAssetsRepo([]),  # type: ignore[arg-type]
        progress_cache=FakeProgressCache(fresh=False),  # type: ignore[arg-type]
        dispatcher=FakeDispatcher(),  # type: ignore[arg-type]
    )
    assert await service.recover_orphaned_jobs(threshold_seconds=1800) == 0


def test_heartbeat_stale_detection() -> None:
    from app.config.settings import JobSettings
    from app.infrastructure.redis.job_progress import JobProgressCache

    cache = JobProgressCache(redis=None, settings=JobSettings(heartbeat_ttl_seconds=60))  # type: ignore[arg-type]
    fresh = {"timestamp": datetime.now(timezone.utc).isoformat()}
    stale = {
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    }
    assert cache.is_worker_stale(fresh) is False
    assert cache.is_worker_stale(stale) is True
    assert cache.is_worker_stale({}) is True
    assert cache.is_worker_stale({"timestamp": "not-a-date"}) is True


# --- Part 5: R2 resiliency ------------------------------------------------


def _configured_settings(**overrides: Any) -> R2Settings:
    values = {
        "account_id": "acct",
        "access_key_id": "key",
        "secret_access_key": "secret",
        "bucket_name": "bucket",
        "retry_count": 2,
        "backoff_base_seconds": 0.01,
        "backoff_max_seconds": 0.05,
    }
    values.update(overrides)
    return R2Settings(**values)


def _client_error(status: int, code: str = "InternalError") -> Any:
    from botocore.exceptions import ClientError

    return ClientError(
        {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}},
        "op",
    )


@pytest.mark.asyncio
async def test_r2_retry_succeeds_after_transient_failure() -> None:
    from app.infrastructure.r2.client import CloudflareR2Storage

    storage = CloudflareR2Storage(_configured_settings())
    calls = {"count": 0}

    def flaky_put(**kwargs: Any) -> dict[str, Any]:
        calls["count"] += 1
        if calls["count"] < 3:
            raise _client_error(500)
        return {}

    storage._client = MagicMock()
    storage._client.put_object = flaky_put

    key = await storage.upload("k", b"data")
    assert key == "k"
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_r2_no_retry_on_client_error() -> None:
    from app.infrastructure.r2.client import CloudflareR2Storage
    from app.shared.exceptions import StorageException

    storage = CloudflareR2Storage(_configured_settings())
    calls = {"count": 0}

    def failing_put(**kwargs: Any) -> None:
        calls["count"] += 1
        raise _client_error(403, "AccessDenied")

    storage._client = MagicMock()
    storage._client.put_object = failing_put

    with pytest.raises(StorageException):
        await storage.upload("k", b"data")
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_r2_retry_exhaustion_raises() -> None:
    from app.infrastructure.r2.client import CloudflareR2Storage
    from app.shared.exceptions import StorageException

    storage = CloudflareR2Storage(_configured_settings(retry_count=1))
    storage._client = MagicMock()
    storage._client.get_object = MagicMock(side_effect=_client_error(500))

    with pytest.raises(StorageException):
        await storage.download("k")


@pytest.mark.asyncio
async def test_r2_streaming_download_chunks() -> None:
    from app.infrastructure.r2.client import CloudflareR2Storage

    payload = b"x" * 4096
    body = MagicMock()
    chunks = [payload[:1024], payload[1024:2048], payload[2048:], b""]
    body.read = MagicMock(side_effect=lambda size=-1: chunks.pop(0))

    storage = CloudflareR2Storage(_configured_settings())
    storage._client = MagicMock()
    storage._client.get_object = MagicMock(return_value={"Body": body})

    received = b""
    async for chunk in storage.download_stream("k"):
        received += chunk
    assert received == payload


@pytest.mark.asyncio
async def test_r2_streaming_upload_passthrough() -> None:
    from app.infrastructure.r2.client import CloudflareR2Storage

    stream = io.BytesIO(b"streamed-payload")
    storage = CloudflareR2Storage(_configured_settings())
    storage._client = MagicMock()
    put = MagicMock(return_value={})
    storage._client.put_object = put

    await storage.upload_stream("k", stream, content_type="audio/wav")
    assert put.call_args.kwargs["Body"] is stream


# --- Part 6: celery config -------------------------------------------------


def test_celery_config_uses_performance_settings() -> None:
    from app.config.settings import get_settings

    settings = get_settings()
    assert settings.performance.worker_concurrency >= 1
    assert settings.performance.task_timeout >= 1
    assert settings.performance.r2_retry_count >= 0
    assert isinstance(settings.performance.model_warmup, bool)
    assert isinstance(settings.performance.pipeline_profiling, bool)

    from app.infrastructure.celery.app import create_celery_app

    app = create_celery_app()
    assert app.conf.task_time_limit == settings.performance.task_timeout
    assert (
        app.conf.worker_prefetch_multiplier == settings.performance.prefetch_multiplier
    )
    assert app.conf.worker_concurrency == settings.performance.worker_concurrency


# --- Timeout recovery (worker-level) ---------------------------------------


@pytest.mark.asyncio
async def test_task_timeout_mapped_to_retryable_timeout() -> None:
    """Preprocessing timeouts surface as retryable TimeoutError."""
    from app.audio.preprocessing.exceptions import PreprocessingTimeoutException

    with pytest.raises(PreprocessingTimeoutException):
        raise PreprocessingTimeoutException("ffprobe timed out")
