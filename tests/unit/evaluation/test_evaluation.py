"""Unit tests for the Evaluation workflow (Sprint 10)."""

from __future__ import annotations

import csv as csv_module
import io as io_module
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

import app.shared.database.models_registry  # noqa: F401
from app.audio.models import AudioAsset, AudioBatch
from app.evaluation.exceptions import (
    BatchNotFoundForEvaluationException,
    BatchNotRunnableException,
    ExportNotFoundException,
)
from app.evaluation.exporter import (
    BatchExporter,
    exports_csv_key,
    exports_json_key,
)
from app.evaluation.factory import build_evaluation_service
from app.evaluation.metrics import BatchMetricsCalculator
from app.evaluation.pipeline import EvaluationPipeline
from app.evaluation.runner import BatchRunner
from app.evaluation.service import EvaluationService
from app.jobs.models import Job
from app.shared.domain.enums import AudioStatus, BatchStatus, JobStatus


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload(self, key: str, data: bytes, **_: Any) -> str:
        self.objects[key] = data
        return key

    async def download(self, key: str) -> bytes:
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key]

    async def generate_signed_url(self, key: str, expires_in: int = 3600) -> str:
        return f"https://signed.example.test/{key}?exp={expires_in}"

    async def health_check(self) -> bool:
        return True


class FakeBatches:
    def __init__(self, batch: AudioBatch | None) -> None:
        self.batch = batch

    async def find_by_id(self, batch_id: Any) -> AudioBatch | None:
        return self.batch if self.batch and self.batch.id == batch_id else None


class FakeJobsRepo:
    def __init__(self, job: Job | None) -> None:
        self.job = job

    async def find_by_batch(self, batch_id: Any) -> Job | None:
        return self.job if self.job and self.job.batch_id == batch_id else None


class FakeJobService:
    def __init__(self, job: Job) -> None:
        self.job = job
        self.queue_calls = 0

    async def create_job(self, batch_id: Any) -> Job:
        return self.job

    async def queue_job(self, job_id: Any, countdown: int = 0) -> Job:
        self.queue_calls += 1
        self.job.status = JobStatus.QUEUED
        return self.job


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


class FakeMetricsRepo:
    def __init__(self) -> None:
        self.saved: dict[Any, Any] = {}

    async def find_by_batch(self, batch_id: Any) -> Any:
        return self.saved.get(batch_id)

    async def upsert(self, batch_id: Any, **kwargs: Any) -> Any:
        record = type("MetricsRecord", (), {"batch_id": batch_id, **kwargs})()
        self.saved[batch_id] = record
        return record


class FakePredictionExport:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.csv_calls = 0

    async def export_csv(self, batch_id: Any) -> str:
        self.csv_calls += 1
        buffer = io_module.StringIO()
        writer = csv_module.writer(buffer)
        writer.writerow(["filename", "result_json"])
        for row in self._rows:
            writer.writerow([row["filename"], json.dumps(row["result"])])
        return buffer.getvalue()

    async def export_json(self, batch_id: Any) -> list[dict[str, Any]]:
        return list(self._rows)


def _batch(*, with_assets: bool = True) -> AudioBatch:
    batch = AudioBatch(
        original_filename="calls.zip",
        total_files=2,
        status=BatchStatus.VALIDATED,
    )
    batch.id = uuid4()
    if with_assets:
        assets = []
        for name in ("a.wav", "b.wav"):
            asset = AudioAsset(
                batch_id=batch.id,
                filename=name,
                format="wav",
                extension="wav",
                mime_type="audio/wav",
                size_bytes=100,
                checksum_sha256="0" * 64,
                uploaded_at=datetime.now(timezone.utc) - timedelta(seconds=10),
                storage_key=f"uploads/{batch.id}/original/{name}",
                processing_status=AudioStatus.COMPLETED,
            )
            asset.id = uuid4()
            assets.append(asset)
        batch.assets = assets
    else:
        batch.assets = []
    return batch


def _job(batch_id: Any, status: JobStatus = JobStatus.PENDING) -> Job:
    job = Job(
        batch_id=batch_id,
        status=status,
        progress=0,
        total_files=2,
        processed_files=0,
        failed_files=0,
    )
    job.id = uuid4()
    return job


def _prediction_record(asset_id: Any, *, confidence: float, completed: datetime) -> Any:
    return type(
        "PredictionRecord",
        (),
        {
            "audio_asset_id": asset_id,
            "confidence": confidence,
            "prediction_completed_at": completed,
            "prediction_json": {
                "emotional_tone": "NEUTRAL",
                "emotional_intensity": "LOW",
                "background_noise_present": False,
                "background_noise_type": "NONE",
                "background_noise_severity": "NONE",
                "audio_quality": "CLEAR",
                "speaker_overlap_present": False,
                "long_silence_present": False,
                "confidence": confidence,
            },
            "audio_asset": None,
        },
    )()


ASSESSMENT_KEYS = {
    "emotional_tone",
    "emotional_intensity",
    "background_noise_present",
    "background_noise_type",
    "background_noise_severity",
    "audio_quality",
    "speaker_overlap_present",
    "long_silence_present",
    "confidence",
}


# --- Batch execution -----------------------------------------------------


@pytest.mark.asyncio
async def test_run_batch_queues_job() -> None:
    batch = _batch()
    job = _job(batch.id)
    job_service = FakeJobService(job)
    runner = BatchRunner(batches=FakeBatches(batch), jobs=job_service)  # type: ignore[arg-type]
    result = await runner.run(batch.id)
    assert result.queued is True
    assert result.already_running is False
    assert job_service.queue_calls == 1
    assert result.job_id == job.id


@pytest.mark.asyncio
async def test_run_batch_duplicate_prevented() -> None:
    batch = _batch()
    job = _job(batch.id, status=JobStatus.RUNNING)
    job_service = FakeJobService(job)
    runner = BatchRunner(batches=FakeBatches(batch), jobs=job_service)  # type: ignore[arg-type]
    result = await runner.run(batch.id)
    assert result.queued is False
    assert result.already_running is True
    assert job_service.queue_calls == 0


@pytest.mark.asyncio
async def test_run_batch_not_found() -> None:
    runner = BatchRunner(
        batches=FakeBatches(None),  # type: ignore[arg-type]
        jobs=FakeJobService(_job(uuid4())),  # type: ignore[arg-type]
    )
    with pytest.raises(BatchNotFoundForEvaluationException):
        await runner.run(uuid4())


@pytest.mark.asyncio
async def test_run_batch_empty_batch_rejected() -> None:
    batch = _batch(with_assets=False)
    runner = BatchRunner(
        batches=FakeBatches(batch),  # type: ignore[arg-type]
        jobs=FakeJobService(_job(batch.id)),  # type: ignore[arg-type]
    )
    with pytest.raises(BatchNotRunnableException):
        await runner.run(batch.id)


# --- Status / progress ---------------------------------------------------


@pytest.mark.asyncio
async def test_status_with_progress_estimate() -> None:
    batch = _batch()
    job = _job(batch.id, status=JobStatus.RUNNING)
    job.progress = 50
    job.processed_files = 1
    job.started_at = datetime.now(timezone.utc) - timedelta(seconds=30)
    service = EvaluationService(
        batches=FakeBatches(batch),  # type: ignore[arg-type]
        jobs=FakeJobsRepo(job),  # type: ignore[arg-type]
        runner=None,  # type: ignore[arg-type]
        pipeline=None,  # type: ignore[arg-type]
        exporter=None,  # type: ignore[arg-type]
        metrics_repo=FakeMetricsRepo(),  # type: ignore[arg-type]
        predictions_export=None,  # type: ignore[arg-type]
    )
    status = await service.get_status(batch.id)
    assert status.job_id == job.id
    assert status.status == "RUNNING"
    assert status.progress == 50
    assert status.estimated_remaining_seconds is not None
    assert 25.0 <= status.estimated_remaining_seconds <= 35.0


@pytest.mark.asyncio
async def test_status_without_job() -> None:
    batch = _batch()
    service = EvaluationService(
        batches=FakeBatches(batch),  # type: ignore[arg-type]
        jobs=FakeJobsRepo(None),  # type: ignore[arg-type]
        runner=None,  # type: ignore[arg-type]
        pipeline=None,  # type: ignore[arg-type]
        exporter=None,  # type: ignore[arg-type]
        metrics_repo=FakeMetricsRepo(),  # type: ignore[arg-type]
        predictions_export=None,  # type: ignore[arg-type]
    )
    status = await service.get_status(batch.id)
    assert status.job_id is None
    assert status.progress == 0
    assert status.estimated_remaining_seconds is None


# --- Metrics -------------------------------------------------------------


def test_metrics_calculator_partial_failures() -> None:
    batch = _batch()
    uploaded = batch.assets[0].uploaded_at
    predictions = [
        _prediction_record(
            batch.assets[0].id,
            confidence=0.8,
            completed=uploaded + timedelta(milliseconds=5000),
        )
    ]
    metrics = BatchMetricsCalculator().calculate(
        assets=batch.assets,
        predictions=predictions,  # type: ignore[arg-type]
    )
    assert metrics.total_audio == 2
    assert metrics.successful_predictions == 1
    assert metrics.failed_predictions == 1
    assert metrics.success_rate == 0.5
    assert metrics.average_processing_time_ms == 5000.0
    assert metrics.min_processing_time_ms == 5000.0
    assert metrics.max_processing_time_ms == 5000.0
    assert metrics.average_confidence == 0.8


def test_metrics_calculator_empty_batch() -> None:
    metrics = BatchMetricsCalculator().calculate(assets=[], predictions=[])
    assert metrics.total_audio == 0
    assert metrics.success_rate == 0.0
    assert metrics.average_processing_time_ms is None
    assert metrics.average_confidence is None


@pytest.mark.asyncio
async def test_pipeline_persists_metrics_and_uploads_exports() -> None:
    batch = _batch()
    uploaded = batch.assets[0].uploaded_at
    predictions = [
        _prediction_record(
            batch.assets[0].id,
            confidence=0.9,
            completed=uploaded + timedelta(milliseconds=2000),
        )
    ]
    storage = FakeStorage()
    rows = [{"filename": "a.wav", "result": dict.fromkeys(ASSESSMENT_KEYS, "x")}]
    pipeline = EvaluationPipeline(
        assets=FakeAssets(batch.assets),  # type: ignore[arg-type]
        predictions=FakePredictions(predictions),  # type: ignore[arg-type]
        metrics_repo=FakeMetricsRepo(),  # type: ignore[arg-type]
        calculator=BatchMetricsCalculator(),
        exporter=BatchExporter(
            storage=storage,  # type: ignore[arg-type]
            predictions_export=FakePredictionExport(rows),  # type: ignore[arg-type]
        ),
    )
    metrics = await pipeline.finalize_batch(batch.id)
    assert metrics.total_audio == 2
    assert metrics.successful_predictions == 1
    assert exports_csv_key(batch.id) in storage.objects
    assert exports_json_key(batch.id) in storage.objects


@pytest.mark.asyncio
async def test_export_generation_idempotent() -> None:
    batch = _batch()
    storage = FakeStorage()
    export = FakePredictionExport([])
    exporter = BatchExporter(
        storage=storage,  # type: ignore[arg-type]
        predictions_export=export,  # type: ignore[arg-type]
    )
    await exporter.generate_and_upload(batch.id)
    assert export.csv_calls == 1
    objects_before = dict(storage.objects)
    await exporter.generate_and_upload(batch.id)
    assert export.csv_calls == 1
    assert storage.objects == objects_before

    # Regeneration explicitly refreshes artifacts.
    await exporter.generate_and_upload(batch.id, regenerate=True)
    assert export.csv_calls == 2


@pytest.mark.asyncio
async def test_signed_exports_and_missing() -> None:
    batch = _batch()
    storage = FakeStorage()
    exporter = BatchExporter(
        storage=storage,  # type: ignore[arg-type]
        predictions_export=FakePredictionExport([]),  # type: ignore[arg-type]
    )
    with pytest.raises(ExportNotFoundException):
        await exporter.get_signed_exports(batch.id)

    await exporter.generate_and_upload(batch.id)
    items = await exporter.get_signed_exports(batch.id)
    assert len(items) == 2
    names = {item["name"] for item in items}
    assert names == {"results.csv", "results.json"}
    assert all(
        str(item["url"]).startswith("https://signed.example.test/") for item in items
    )


# --- CSV / JSON export content -------------------------------------------


@pytest.mark.asyncio
async def test_csv_export_exact_shape() -> None:
    batch = _batch()
    rows = [
        {
            "filename": "a.wav",
            "result": {
                "emotional_tone": "NEUTRAL",
                "emotional_intensity": "LOW",
                "background_noise_present": False,
                "background_noise_type": "NONE",
                "background_noise_severity": "NONE",
                "audio_quality": "CLEAR",
                "speaker_overlap_present": False,
                "long_silence_present": False,
                "confidence": 0.82,
            },
        }
    ]
    service = EvaluationService(
        batches=FakeBatches(batch),  # type: ignore[arg-type]
        jobs=FakeJobsRepo(None),  # type: ignore[arg-type]
        runner=None,  # type: ignore[arg-type]
        pipeline=None,  # type: ignore[arg-type]
        exporter=None,  # type: ignore[arg-type]
        metrics_repo=FakeMetricsRepo(),  # type: ignore[arg-type]
        predictions_export=FakePredictionExport(rows),  # type: ignore[arg-type]
    )
    csv_text = await service.export_csv(batch.id)
    parsed = list(csv_module.reader(io_module.StringIO(csv_text)))
    assert parsed[0] == ["filename", "result_json"]
    result = json.loads(parsed[1][1])
    assert set(result.keys()) == ASSESSMENT_KEYS
    assert result["confidence"] == 0.82

    payload = await service.export_json(batch.id)
    assert set(payload[0]["result"].keys()) == ASSESSMENT_KEYS


# --- Factory -------------------------------------------------------------


def test_factory_builds_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.evaluation import factory

    monkeypatch.setattr(
        factory, "CloudflareR2Storage", lambda *args, **kwargs: FakeStorage()
    )
    monkeypatch.setattr(factory, "build_job_service", lambda session: None)
    service = build_evaluation_service(session=None)  # type: ignore[arg-type]
    assert isinstance(service, EvaluationService)
