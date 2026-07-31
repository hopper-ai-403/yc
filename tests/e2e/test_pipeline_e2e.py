"""End-to-end pipeline validation (Sprint 12, Part 1/2/3).

Runs the complete stage chain in-process with deterministic substitutes only
at true external boundaries (ffmpeg/ffprobe binaries, SER model weights, R2):

Upload → Preprocessing → Analysis → Technical → Acoustic → Speech →
Prediction → CSV/JSON Export → Metrics → Benchmark.
"""

from __future__ import annotations

import csv as csv_module
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import numpy as np
import pytest
import soundfile as sf

import app.shared.database.models_registry  # noqa: F401
from app.ai.acoustic.analyzer import AcousticAnalyzer
from app.ai.acoustic.factory import (
    build_noise_classifier,
    build_noise_detector,
    build_severity_estimator,
)
from app.ai.acoustic.pipeline import AcousticPipeline
from app.ai.acoustic.service import AcousticService
from app.ai.speech.analyzer import SpeechAnalyzer
from app.ai.speech.model import LabelScore, ModelMetadata, ModelPrediction
from app.ai.speech.pipeline import SpeechPipeline
from app.ai.speech.service import SpeechService
from app.ai.technical.analyzer import TechnicalAnalyzer
from app.ai.technical.factory import build_overlap_detector
from app.ai.technical.pipeline import TechnicalPipeline
from app.ai.technical.quality import AudioQualityAnalyzer
from app.ai.technical.service import TechnicalService
from app.ai.technical.silence import LongSilenceDetector
from app.audio.analysis.features import FeatureExtractor
from app.audio.analysis.pipeline import AnalysisPipeline
from app.audio.analysis.service import AnalysisService
from app.audio.analysis.vad import EnergyVAD
from app.audio.models import AudioAsset, AudioBatch
from app.audio.preprocessing.exceptions import FFprobeException
from app.audio.preprocessing.metadata import ProbeFormat, ProbeResult, ProbeStream
from app.audio.preprocessing.pipeline import PreprocessingPipeline
from app.audio.preprocessing.service import PreprocessingService
from app.audio.preprocessing.validator import AudioValidator
from app.config.settings import (
    AcousticSettings,
    AnalysisSettings,
    PredictionSettings,
    PreprocessingSettings,
    SpeechSettings,
    TechnicalSettings,
)
from app.evaluation.exporter import BatchExporter, exports_csv_key, exports_json_key
from app.evaluation.metrics import BatchMetricsCalculator
from app.evaluation.pipeline import EvaluationPipeline
from app.jobs.models import Job
from app.prediction.aggregator import PredictionAggregator
from app.prediction.builder import PredictionBuilder
from app.prediction.confidence import WeightedConfidenceEstimator
from app.prediction.export import PredictionExportService
from app.prediction.models import Prediction
from app.prediction.pipeline import PredictionPipeline
from app.prediction.service import PredictionService
from app.prediction.validator import PredictionValidator
from app.shared.domain.enums import AudioStatus, BatchStatus, JobStatus
from app.system.benchmark import BenchmarkRunner

ASSESSMENT_FIELDS_IN_ORDER = (
    "emotional_tone",
    "emotional_intensity",
    "background_noise_present",
    "background_noise_type",
    "background_noise_severity",
    "audio_quality",
    "speaker_overlap_present",
    "long_silence_present",
    "confidence",
)


def _synthetic_wav(seconds: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Speech-like waveform: alternating tone bursts and silence."""
    frames = int(seconds * sample_rate)
    t = np.arange(frames) / sample_rate
    burst = 0.4 * np.sin(2 * np.pi * 220.0 * t)
    gate = (np.sin(2 * np.pi * 2.0 * t) > 0).astype(np.float32)
    waveform = (burst * gate).astype(np.float32)
    buffer = io.BytesIO()
    sf.write(buffer, waveform, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


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

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def list(self, prefix: str = "", *, max_keys: int = 1000) -> list[str]:
        return [k for k in self.objects if k.startswith(prefix)][:max_keys]

    async def generate_signed_url(self, key: str, expires_in: int = 3600) -> str:
        return f"https://signed.example.test/{key}?exp={expires_in}"

    async def health_check(self) -> bool:
        return True


class FakeProbe:
    def probe(self, path: Path) -> ProbeResult:
        payload = path.read_bytes()
        if not payload.startswith(b"RIFF"):
            raise FFprobeException(
                "ffprobe could not decode audio stream",
                details={"path": path.name},
            )
        if path.name.startswith("normalized"):
            return ProbeResult(
                streams=[
                    ProbeStream(
                        codec_type="audio",
                        codec_name="pcm_s16le",
                        sample_rate="16000",
                        channels=1,
                        duration="2.0",
                    )
                ],
                format=ProbeFormat(format_name="wav", duration="2.0", size="64000"),
            )
        return ProbeResult(
            streams=[
                ProbeStream(
                    codec_type="audio",
                    codec_name="pcm_s16le",
                    sample_rate="16000",
                    channels=1,
                    duration="2.0",
                    bit_rate="256000",
                )
            ],
            format=ProbeFormat(format_name="wav", duration="2.0", size="64000"),
        )


class FakeFFmpeg:
    def __init__(self, normalized_wav: bytes) -> None:
        self._normalized_wav = normalized_wav

    def measure_levels(self, path: Path) -> tuple[float | None, float | None]:
        del path
        return -1.5, -18.0

    def normalize(self, input_path: Path, output_path: Path) -> None:
        del input_path
        output_path.write_bytes(self._normalized_wav)


class FakeNormalizer:
    target_sample_rate = 16000
    target_channels = 1
    target_codec = "pcm_s16le"

    def __init__(self, ffmpeg: FakeFFmpeg) -> None:
        self._ffmpeg = ffmpeg

    def normalize(self, input_path: Path, output_path: Path) -> Path:
        self._ffmpeg.normalize(input_path, output_path)
        return output_path


class MockSpeechEmotionModel:
    def __init__(self, settings: SpeechSettings) -> None:
        self._settings = settings
        self.loaded = False

    def load(self) -> None:
        self.loaded = True

    def predict(self, waveform: np.ndarray, sample_rate: int) -> ModelPrediction:
        assert self.loaded
        return ModelPrediction(
            scores=[
                LabelScore(label="neu", probability=0.71),
                LabelScore(label="hap", probability=0.19),
                LabelScore(label="ang", probability=0.10),
            ]
        )

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            name=self._settings.model_name,
            backend="mock",
            labels=["neu", "hap", "ang"],
        )


class SharedFakeAssetRepo:
    """Mutable in-memory AudioRepository shared across all stage services."""

    def __init__(self, assets: list[AudioAsset]) -> None:
        self.assets: dict[UUID, AudioAsset] = {a.id: a for a in assets}

    async def find_by_id(self, asset_id: Any) -> AudioAsset | None:
        return self.assets.get(asset_id)

    async def find_by_batch(self, batch_id: Any) -> list[AudioAsset]:
        return [a for a in self.assets.values() if a.batch_id == batch_id]

    async def update_status(self, asset_id: Any, status: AudioStatus) -> None:
        asset = self.assets[asset_id]
        asset.processing_status = status

    async def save_preprocessing_result(
        self, asset_id: Any, **kwargs: Any
    ) -> AudioAsset:
        asset = self.assets[asset_id]
        asset.duration = kwargs["duration"]
        asset.sample_rate = kwargs["sample_rate"]
        asset.channels = kwargs["channels"]
        asset.normalized_storage_key = kwargs["normalized_storage_key"]
        asset.metadata_json = dict(kwargs["metadata_json"])
        asset.is_preprocessed = True
        asset.preprocessed_at = kwargs["preprocessed_at"]
        return asset

    async def save_analysis_result(self, asset_id: Any, **kwargs: Any) -> AudioAsset:
        asset = self.assets[asset_id]
        asset.analysis_storage_key = kwargs["analysis_storage_key"]
        asset.analysis_version = kwargs["analysis_version"]
        asset.analysis_json = dict(kwargs["analysis_json"])
        asset.analysis_completed = True
        asset.analysis_completed_at = kwargs["analysis_completed_at"]
        return asset

    async def save_technical_result(self, asset_id: Any, **kwargs: Any) -> AudioAsset:
        asset = self.assets[asset_id]
        asset.technical_version = kwargs["technical_version"]
        asset.technical_json = dict(kwargs["technical_json"])
        asset.technical_completed = True
        asset.technical_completed_at = kwargs["technical_completed_at"]
        return asset

    async def save_acoustic_result(self, asset_id: Any, **kwargs: Any) -> AudioAsset:
        asset = self.assets[asset_id]
        asset.acoustic_version = kwargs["acoustic_version"]
        asset.acoustic_json = dict(kwargs["acoustic_json"])
        asset.acoustic_completed = True
        asset.acoustic_completed_at = kwargs["acoustic_completed_at"]
        return asset

    async def save_speech_result(self, asset_id: Any, **kwargs: Any) -> AudioAsset:
        asset = self.assets[asset_id]
        asset.speech_version = kwargs["speech_version"]
        asset.speech_json = dict(kwargs["speech_json"])
        asset.speech_completed = True
        asset.speech_completed_at = kwargs["speech_completed_at"]
        return asset

    async def save_timing(self, asset_id: Any, *, timing_json: dict) -> AudioAsset:
        asset = self.assets[asset_id]
        asset.timing_json = dict(timing_json)
        return asset


class SharedFakePredictionRepo:
    def __init__(self, assets: SharedFakeAssetRepo) -> None:
        self._assets = assets
        self.records: list[Prediction] = []

    async def find_by_audio_asset(self, audio_asset_id: Any) -> Prediction | None:
        return next(
            (p for p in self.records if p.audio_asset_id == audio_asset_id), None
        )

    async def find_by_batch(self, batch_id: Any) -> list[Prediction]:
        return [p for p in self.records if p.audio_asset.batch_id == batch_id]

    async def save_engine_result(
        self, audio_asset_id: Any, **kwargs: Any
    ) -> Prediction:
        asset = self._assets.assets[audio_asset_id]
        payload = dict(kwargs["prediction_json"])
        prediction = Prediction(
            audio_asset_id=asset.id,
            emotional_tone=payload["emotional_tone"],
            emotional_intensity=payload["emotional_intensity"],
            background_noise_present=payload["background_noise_present"],
            background_noise_type=payload["background_noise_type"],
            background_noise_severity=payload["background_noise_severity"],
            audio_quality=payload["audio_quality"],
            speaker_overlap=payload["speaker_overlap_present"],
            long_silence=payload["long_silence_present"],
            confidence=payload["confidence"],
            prediction_version=kwargs["prediction_version"],
            prediction_json=payload,
            internal_prediction_json=kwargs["internal_prediction_json"],
            confidence_breakdown=kwargs["confidence_breakdown"],
            prediction_completed_at=kwargs["prediction_completed_at"],
        )
        prediction.audio_asset = asset
        prediction.id = uuid4()
        self.records = [
            p for p in self.records if p.audio_asset_id != prediction.audio_asset_id
        ]
        self.records.append(prediction)
        return prediction


class FakeMetricsRepo:
    def __init__(self) -> None:
        self.saved: dict[Any, Any] = {}

    async def find_by_batch(self, batch_id: Any) -> Any:
        return self.saved.get(batch_id)

    async def upsert(self, batch_id: Any, **kwargs: Any) -> Any:
        record = type("MetricsRecord", (), {"batch_id": batch_id, **kwargs})()
        self.saved[batch_id] = record
        return record


class FakeJobRepo:
    def __init__(self, job: Job) -> None:
        self._job = job

    async def find_by_batch(self, batch_id: Any) -> Job | None:
        return self._job if self._job.batch_id == batch_id else None


class FakeBatchRepo:
    def __init__(self, batch: AudioBatch) -> None:
        self._batch = batch

    async def find_by_id(self, batch_id: Any) -> AudioBatch | None:
        return self._batch if self._batch.id == batch_id else None


class PipelineHarness:
    """End-to-end stage chain with external boundaries substituted."""

    def __init__(self) -> None:
        self.storage = FakeStorage()
        self.preprocessing_settings = PreprocessingSettings()
        self.analysis_settings = AnalysisSettings()
        self.technical_settings = TechnicalSettings()
        self.acoustic_settings = AcousticSettings()
        self.speech_settings = SpeechSettings()
        self.prediction_settings = PredictionSettings(internal_prediction_enabled=True)

    def make_batch(self, *, file_count: int = 3, corrupt_last: bool = False) -> tuple[
        AudioBatch,
        list[AudioAsset],
    ]:
        batch = AudioBatch(
            original_filename="sample.zip",
            total_files=file_count,
            status=BatchStatus.VALIDATED,
        )
        batch.id = uuid4()
        assets: list[AudioAsset] = []
        for index in range(file_count):
            filename = f"call_{index}.wav"
            payload = (
                b"NOT-AUDIO-GARBAGE"
                if corrupt_last and index == file_count - 1
                else _synthetic_wav()
            )
            asset = AudioAsset(
                batch_id=batch.id,
                filename=filename,
                format="wav",
                extension="wav",
                mime_type="audio/wav",
                size_bytes=len(payload),
                checksum_sha256="0" * 64,
                uploaded_at=datetime.now(timezone.utc),
                storage_key=f"uploads/{batch.id}/original/{filename}",
                processing_status=AudioStatus.VALIDATED,
            )
            asset.id = uuid4()
            assets.append(asset)
            self.storage.objects[asset.storage_key] = payload
        batch.assets = assets
        return batch, assets

    def build_services(self, repo: SharedFakeAssetRepo) -> dict[str, Any]:
        preprocessing = PreprocessingService(
            assets=repo,  # type: ignore[arg-type]
            pipeline=PreprocessingPipeline(
                settings=self.preprocessing_settings,
                storage=self.storage,  # type: ignore[arg-type]
                ffprobe=FakeProbe(),  # type: ignore[arg-type]
                ffmpeg=FakeFFmpeg(_synthetic_wav()),  # type: ignore[arg-type]
                validator=AudioValidator(self.preprocessing_settings),
                normalizer=FakeNormalizer(FakeFFmpeg(_synthetic_wav())),  # type: ignore[arg-type]
            ),
        )
        analysis = AnalysisService(
            assets=repo,  # type: ignore[arg-type]
            pipeline=AnalysisPipeline(
                settings=self.analysis_settings,
                storage=self.storage,  # type: ignore[arg-type]
                vad=EnergyVAD(),
                features=FeatureExtractor(),
            ),
            storage=self.storage,  # type: ignore[arg-type]
        )
        technical = TechnicalService(
            assets=repo,  # type: ignore[arg-type]
            pipeline=TechnicalPipeline(
                storage=self.storage,  # type: ignore[arg-type]
                analyzer=TechnicalAnalyzer(
                    silence=LongSilenceDetector(self.technical_settings),
                    quality=AudioQualityAnalyzer(self.technical_settings),
                    overlap=build_overlap_detector(self.technical_settings),
                ),
            ),
        )
        acoustic = AcousticService(
            assets=repo,  # type: ignore[arg-type]
            pipeline=AcousticPipeline(
                storage=self.storage,  # type: ignore[arg-type]
                analyzer=AcousticAnalyzer(
                    detector=build_noise_detector(self.acoustic_settings),
                    classifier=build_noise_classifier(self.acoustic_settings),
                    severity=build_severity_estimator(self.acoustic_settings),
                ),
            ),
        )
        model = MockSpeechEmotionModel(self.speech_settings)
        model.load()
        speech = SpeechService(
            assets=repo,  # type: ignore[arg-type]
            pipeline=SpeechPipeline(
                storage=self.storage,  # type: ignore[arg-type]
                analyzer=SpeechAnalyzer(model=model, settings=self.speech_settings),
                settings=self.speech_settings,
            ),
        )
        predictions_repo = SharedFakePredictionRepo(repo)
        prediction = PredictionService(
            assets=repo,  # type: ignore[arg-type]
            predictions=predictions_repo,  # type: ignore[arg-type]
            pipeline=PredictionPipeline(
                storage=self.storage,  # type: ignore[arg-type]
                aggregator=PredictionAggregator(),
                confidence=WeightedConfidenceEstimator(self.prediction_settings),
                builder=PredictionBuilder(),
                validator=PredictionValidator(
                    confidence_rounding=self.prediction_settings.confidence_rounding,
                ),
                settings=self.prediction_settings,
            ),
            settings=self.prediction_settings,
        )
        export = PredictionExportService(predictions=predictions_repo)  # type: ignore[arg-type]
        exporter = BatchExporter(
            storage=self.storage,  # type: ignore[arg-type]
            predictions_export=export,
        )
        metrics_repo = FakeMetricsRepo()
        return {
            "preprocessing": preprocessing,
            "analysis": analysis,
            "technical": technical,
            "acoustic": acoustic,
            "speech": speech,
            "prediction": prediction,
            "predictions_repo": predictions_repo,
            "export": export,
            "exporter": exporter,
            "metrics_repo": metrics_repo,
        }

    async def run_asset(self, asset: AudioAsset, services: dict[str, Any]) -> bool:
        """Run every stage for one asset; return True on success."""
        try:
            await services["preprocessing"].preprocess_audio(asset.id)
            await services["analysis"].analyze_audio(asset.id)
            await services["technical"].analyze_audio(asset.id)
            await services["acoustic"].analyze_audio(asset.id)
            await services["speech"].analyze_audio(asset.id)
            await services["prediction"].generate_prediction(
                asset.id,
                profile={"stages": [], "source": "e2e"},
            )
        except Exception:
            asset.processing_status = AudioStatus.FAILED
            return False
        asset.processing_status = AudioStatus.COMPLETED
        asset.timing_json = {
            "preprocessing_duration_ms": 10.0,
            "analysis_duration_ms": 20.0,
            "technical_duration_ms": 5.0,
            "acoustic_duration_ms": 5.0,
            "speech_duration_ms": 30.0,
            "prediction_duration_ms": 5.0,
            "total_pipeline_duration_ms": 75.0,
        }
        return True


def test_csv_output_exact_shape() -> None:
    """Part 2: CSV header, key set/order, booleans, confidence precision."""
    assert ASSESSMENT_FIELDS_IN_ORDER == (
        "emotional_tone",
        "emotional_intensity",
        "background_noise_present",
        "background_noise_type",
        "background_noise_severity",
        "audio_quality",
        "speaker_overlap_present",
        "long_silence_present",
        "confidence",
    )

    from app.prediction.schemas import ASSESSMENT_FIELDS

    assert tuple(ASSESSMENT_FIELDS) == ASSESSMENT_FIELDS_IN_ORDER


@pytest.mark.asyncio
async def test_end_to_end_pipeline_all_stages() -> None:
    """Part 1 + 2: every stage completes; exports validated strictly."""
    harness = PipelineHarness()
    batch, assets = harness.make_batch(file_count=3)
    repo = SharedFakeAssetRepo(assets)
    services = harness.build_services(repo)

    started = datetime.now(timezone.utc)
    for asset in assets:
        assert await harness.run_asset(asset, services) is True
    completed = datetime.now(timezone.utc)

    job = Job(
        batch_id=batch.id,
        status=JobStatus.COMPLETED,
        progress=100,
        total_files=3,
        processed_files=3,
        failed_files=0,
    )
    job.id = uuid4()
    job.started_at = started
    job.completed_at = completed

    # Every stage persisted onto the asset.
    for asset in assets:
        assert asset.is_preprocessed and asset.normalized_storage_key
        assert asset.analysis_completed and asset.analysis_json
        assert asset.technical_completed and asset.technical_json
        assert asset.acoustic_completed and asset.acoustic_json
        assert asset.speech_completed and asset.speech_json
        assert asset.processing_status is AudioStatus.COMPLETED

    predictions = services["predictions_repo"].records
    assert len(predictions) == 3

    # Internal prediction metadata carries the profile.
    for prediction in predictions:
        internal = prediction.internal_prediction_json
        assert internal is not None
        assert internal.get("profile", {}).get("source") == "e2e"

    # CSV export: exact header + strict result_json shape.
    csv_text = await services["export"].export_csv(batch.id)
    rows = list(csv_module.reader(io.StringIO(csv_text)))
    assert rows[0] == ["filename", "result_json"]
    assert len(rows) == 4
    for row in rows[1:]:
        filename, result_raw = row
        assert filename.endswith(".wav")
        result = json.loads(result_raw)
        assert tuple(result.keys()) == ASSESSMENT_FIELDS_IN_ORDER
        assert isinstance(result["background_noise_present"], bool)
        assert isinstance(result["speaker_overlap_present"], bool)
        assert isinstance(result["long_silence_present"], bool)
        confidence = result["confidence"]
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
        assert round(confidence, 2) == confidence  # precision: 2 decimals

    # JSON export: same public shape.
    json_rows = await services["export"].export_json(batch.id)
    assert len(json_rows) == 3
    assert tuple(json_rows[0]["result"].keys()) == ASSESSMENT_FIELDS_IN_ORDER

    # Batch finalize: metrics persisted + exports uploaded idempotently.
    pipeline = EvaluationPipeline(
        assets=repo,  # type: ignore[arg-type]
        predictions=services["predictions_repo"],  # type: ignore[arg-type]
        metrics_repo=services["metrics_repo"],  # type: ignore[arg-type]
        calculator=BatchMetricsCalculator(),
        exporter=services["exporter"],
        jobs=FakeJobRepo(job),  # type: ignore[arg-type]
    )
    metrics = await pipeline.finalize_batch(batch.id)
    assert metrics.total_audio == 3
    assert metrics.successful_predictions == 3
    assert metrics.failed_predictions == 0
    assert metrics.success_rate == 1.0
    assert metrics.batch_duration_ms is not None

    assert exports_csv_key(batch.id) in harness.storage.objects
    assert exports_json_key(batch.id) in harness.storage.objects

    # R2 CSV artifact equals the API CSV output.
    r2_csv = harness.storage.objects[exports_csv_key(batch.id)].decode("utf-8")
    header = next(iter(csv_module.reader(io.StringIO(r2_csv))))
    assert header == ["filename", "result_json"]

    # Signed URLs for exports.
    items = await services["exporter"].get_signed_exports(batch.id)
    assert len(items) == 2
    assert all(
        str(item["url"]).startswith("https://signed.example.test/") for item in items
    )

    # Benchmark over the batch.
    benchmark = await BenchmarkRunner(
        batches=FakeBatchRepo(batch),  # type: ignore[arg-type]
        assets=repo,  # type: ignore[arg-type]
        predictions=services["predictions_repo"],  # type: ignore[arg-type]
        jobs=FakeJobRepo(job),  # type: ignore[arg-type]
    ).run(batch.id)
    assert benchmark.total_files == 3
    assert benchmark.average_latency_ms == 75.0
    assert benchmark.p50_latency_ms == 75.0
    assert benchmark.throughput_files_per_minute is not None
    assert benchmark.failure_rate == 0.0


@pytest.mark.asyncio
async def test_end_to_end_partial_failure_graceful() -> None:
    """Part 3: corrupted audio fails gracefully; batch still completes."""
    harness = PipelineHarness()
    batch, assets = harness.make_batch(file_count=3, corrupt_last=True)
    repo = SharedFakeAssetRepo(assets)
    services = harness.build_services(repo)

    results = [await harness.run_asset(asset, services) for asset in assets]
    assert results == [True, True, False]

    # Exports include only successful predictions.
    csv_text = await services["export"].export_csv(batch.id)
    rows = list(csv_module.reader(io.StringIO(csv_text)))
    assert len(rows) == 3  # header + 2 successes
    filenames = {row[0] for row in rows[1:]}
    assert "call_2.wav" not in filenames

    # Metrics include the failed file.
    pipeline = EvaluationPipeline(
        assets=repo,  # type: ignore[arg-type]
        predictions=services["predictions_repo"],  # type: ignore[arg-type]
        metrics_repo=services["metrics_repo"],  # type: ignore[arg-type]
        calculator=BatchMetricsCalculator(),
        exporter=services["exporter"],
    )
    metrics = await pipeline.finalize_batch(batch.id)
    assert metrics.total_audio == 3
    assert metrics.successful_predictions == 2
    assert metrics.failed_predictions == 1
    assert metrics.success_rate == round(2 / 3, 4)

    # Benchmark reflects partial failure.
    benchmark = await BenchmarkRunner(
        batches=FakeBatchRepo(batch),  # type: ignore[arg-type]
        assets=repo,  # type: ignore[arg-type]
        predictions=services["predictions_repo"],  # type: ignore[arg-type]
        jobs=FakeJobRepo(
            Job(batch_id=batch.id, status=JobStatus.COMPLETED, progress=100)
        ),  # type: ignore[arg-type]
    ).run(batch.id)
    assert benchmark.failed_files == 1
    assert benchmark.failure_rate == round(1 / 3, 4)


@pytest.mark.asyncio
async def test_missing_r2_object_fails_gracefully() -> None:
    """Part 3: missing R2 object surfaces as a handled stage failure."""
    harness = PipelineHarness()
    _batch, assets = harness.make_batch(file_count=1)
    repo = SharedFakeAssetRepo(assets)
    services = harness.build_services(repo)
    harness.storage.objects.clear()  # object vanished

    ok = await harness.run_asset(assets[0], services)
    assert ok is False
    assert assets[0].processing_status is AudioStatus.FAILED
    assert services["predictions_repo"].records == []
