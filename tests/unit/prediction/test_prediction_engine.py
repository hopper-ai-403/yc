"""Unit tests for the Prediction Engine (Sprint 9)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

import app.shared.database.models_registry  # noqa: F401
from app.ai.acoustic.schemas import AcousticResult
from app.ai.speech.schemas import SpeechResult
from app.ai.technical.schemas import QualityBreakdown, TechnicalResult
from app.audio.models import AudioAsset
from app.config.settings import PredictionSettings
from app.prediction.aggregator import PredictionAggregator
from app.prediction.builder import PredictionBuilder
from app.prediction.confidence import WeightedConfidenceEstimator
from app.prediction.exceptions import (
    PredictionAlreadyExistsException,
    PredictionArtifactMissingException,
    PredictionNotFoundException,
    PredictionValidationFailedException,
)
from app.prediction.export import PredictionExportService
from app.prediction.factory import build_prediction_service
from app.prediction.pipeline import PredictionPipeline, prediction_storage_key
from app.prediction.schemas import ASSESSMENT_FIELDS, AnalysisResult, AssessmentPrediction
from app.prediction.service import PredictionService
from app.prediction.validator import PredictionValidator
from app.shared.domain.enums import (
    AudioQuality,
    AudioStatus,
    EmotionIntensity,
    EmotionTone,
    NoiseSeverity,
    NoiseType,
)


def _technical(**overrides: Any) -> TechnicalResult:
    defaults: dict[str, Any] = dict(
        audio_id="a",
        batch_id="b",
        audio_quality=AudioQuality.CLEAR,
        speaker_overlap_present=False,
        long_silence_present=False,
        quality_score=95.0,
        quality_breakdown=QualityBreakdown(total_penalty=5.0),
        overlap_score=0.1,
        overlap_details={},
        silence_details={
            "largest_silence_seconds": 1.0,
            "threshold_largest_silence_seconds": 6.0,
        },
    )
    defaults.update(overrides)
    return TechnicalResult(**defaults)


def _acoustic(**overrides: Any) -> AcousticResult:
    defaults: dict[str, Any] = dict(
        audio_id="a",
        batch_id="b",
        background_noise_present=False,
        background_noise_type=NoiseType.NONE,
        background_noise_severity=NoiseSeverity.NONE,
        noise_score=0.2,
    )
    defaults.update(overrides)
    return AcousticResult(**defaults)


def _speech(**overrides: Any) -> SpeechResult:
    defaults: dict[str, Any] = dict(
        audio_id="a",
        batch_id="b",
        emotional_tone=EmotionTone.NEUTRAL,
        emotional_intensity=EmotionIntensity.LOW,
        top_probability=0.8,
        model_name="mock",
        raw_label="neu",
    )
    defaults.update(overrides)
    return SpeechResult(**defaults)


def _analysis() -> AnalysisResult:
    return AnalysisResult(
        technical=_technical(),
        acoustic=_acoustic(),
        speech=_speech(),
    )


def _settings(**overrides: Any) -> PredictionSettings:
    base = PredictionSettings()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


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

    async def get_signed_url(self, key: str, expires_in: int = 3600) -> str:
        return f"https://example.test/{key}"

    async def health_check(self) -> bool:
        return True


class FakeAssets:
    def __init__(self, asset: AudioAsset) -> None:
        self.asset = asset

    async def find_by_id(self, asset_id: Any) -> AudioAsset | None:
        return self.asset if self.asset.id == asset_id else None


class FakePredictions:
    """In-memory PredictionRepository stand-in."""

    def __init__(self) -> None:
        self.by_asset: dict[Any, Any] = {}

    async def find_by_audio_asset(self, audio_asset_id: Any) -> Any:
        return self.by_asset.get(audio_asset_id)

    async def find_by_batch(self, batch_id: Any) -> list[Any]:
        return [p for p in self.by_asset.values() if p.batch_id == batch_id]

    async def find_by_job(self, job_id: Any) -> list[Any]:
        return [p for p in self.by_asset.values() if p.job_id == job_id]

    async def save_engine_result(self, audio_asset_id: Any, **kwargs: Any) -> Any:
        if audio_asset_id in self.by_asset and not kwargs.get("regenerate"):
            raise PredictionAlreadyExistsException(
                audio_asset_id,
                prediction_id=self.by_asset[audio_asset_id].prediction_id,
            )
        record = type(
            "PredictionRecord",
            (),
            {
                "prediction_id": uuid4(),
                "audio_asset_id": audio_asset_id,
                "batch_id": None,
                "job_id": None,
                "prediction_version": kwargs["prediction_version"],
                "prediction_json": dict(kwargs["prediction_json"]),
                "internal_prediction_json": kwargs.get("internal_prediction_json"),
                "confidence_breakdown": dict(kwargs["confidence_breakdown"]),
                "prediction_completed_at": kwargs["prediction_completed_at"],
            },
        )()
        self.by_asset[audio_asset_id] = record
        return record


def _asset(*, with_results: bool = True) -> AudioAsset:
    batch_id = uuid4()
    audio_id = uuid4()
    asset = AudioAsset(
        batch_id=batch_id,
        filename="call.wav",
        format="wav",
        extension="wav",
        mime_type="audio/wav",
        size_bytes=1024,
        checksum_sha256="f" * 64,
        uploaded_at=datetime.now(timezone.utc),
        storage_key=f"uploads/{batch_id}/original/call.wav",
        processing_status=AudioStatus.PROCESSING,
        is_preprocessed=True,
    )
    asset.id = audio_id
    if with_results:
        asset.technical_completed = True
        asset.technical_json = _technical().to_storage_dict()
        asset.acoustic_completed = True
        asset.acoustic_json = _acoustic().to_storage_dict()
        asset.speech_completed = True
        asset.speech_json = _speech().to_storage_dict()
    return asset


def _pipeline(storage: FakeStorage, settings: PredictionSettings) -> PredictionPipeline:
    return PredictionPipeline(
        storage=storage,  # type: ignore[arg-type]
        aggregator=PredictionAggregator(),
        confidence=WeightedConfidenceEstimator(settings),
        builder=PredictionBuilder(),
        validator=PredictionValidator(confidence_rounding=settings.confidence_rounding),
        settings=settings,
    )


# --- Aggregator ---------------------------------------------------------


def test_aggregator_builds_analysis_result() -> None:
    result = PredictionAggregator().aggregate(_asset())
    assert result.technical.audio_quality is AudioQuality.CLEAR
    assert result.acoustic.background_noise_present is False
    assert result.speech.emotional_tone is EmotionTone.NEUTRAL


def test_aggregator_missing_results() -> None:
    with pytest.raises(PredictionArtifactMissingException) as exc_info:
        PredictionAggregator().aggregate(_asset(with_results=False))
    assert set(exc_info.value.details["missing"]) == {"technical", "acoustic", "speech"}


# --- Builder ------------------------------------------------------------


def test_builder_matches_assessment_schema() -> None:
    settings = _settings()
    breakdown = WeightedConfidenceEstimator(settings).estimate(_analysis())
    prediction = PredictionBuilder().build(_analysis(), breakdown)
    assert set(prediction.to_public_dict().keys()) == set(ASSESSMENT_FIELDS)
    assert prediction.emotional_tone is EmotionTone.NEUTRAL
    assert prediction.audio_quality is AudioQuality.CLEAR


# --- Validator ----------------------------------------------------------


def test_validator_enforces_noise_business_rule() -> None:
    bad = AssessmentPrediction(
        emotional_tone=EmotionTone.NEUTRAL,
        emotional_intensity=EmotionIntensity.LOW,
        background_noise_present=False,
        background_noise_type=NoiseType.MUSIC,
        background_noise_severity=NoiseSeverity.HIGH,
        audio_quality=AudioQuality.CLEAR,
        speaker_overlap_present=False,
        long_silence_present=False,
        confidence=0.8,
    )
    fixed = PredictionValidator().validate(bad)
    assert fixed.background_noise_type is NoiseType.NONE
    assert fixed.background_noise_severity is NoiseSeverity.NONE


def test_validator_confidence_bounds() -> None:
    with pytest.raises(Exception):
        AssessmentPrediction(
            emotional_tone=EmotionTone.NEUTRAL,
            emotional_intensity=EmotionIntensity.LOW,
            background_noise_present=False,
            background_noise_type=NoiseType.NONE,
            background_noise_severity=NoiseSeverity.NONE,
            audio_quality=AudioQuality.CLEAR,
            speaker_overlap_present=False,
            long_silence_present=False,
            confidence=1.5,
        )


def test_validator_rounds_confidence() -> None:
    prediction = AssessmentPrediction(
        emotional_tone=EmotionTone.NEUTRAL,
        emotional_intensity=EmotionIntensity.LOW,
        background_noise_present=False,
        background_noise_type=NoiseType.NONE,
        background_noise_severity=NoiseSeverity.NONE,
        audio_quality=AudioQuality.CLEAR,
        speaker_overlap_present=False,
        long_silence_present=False,
        confidence=0.8261,
    )
    validated = PredictionValidator(confidence_rounding=2).validate(prediction)
    assert validated.confidence == 0.83


# --- Confidence estimator ------------------------------------------------


def test_confidence_weighted_average() -> None:
    settings = _settings(
        confidence_weights={"speech": 1.0, "technical": 0.0, "acoustic": 0.0},
    )
    breakdown = WeightedConfidenceEstimator(settings).estimate(_analysis())
    assert breakdown.overall == breakdown.speech
    assert 0.0 <= breakdown.overall <= 1.0


def test_confidence_breakdown_components() -> None:
    breakdown = WeightedConfidenceEstimator(_settings()).estimate(_analysis())
    assert breakdown.speech == 0.8
    assert 0.0 <= breakdown.technical <= 1.0
    assert breakdown.acoustic == 0.8  # 1 - noise_score when noise absent
    assert breakdown.overall == round(
        0.4 * 0.8 + 0.3 * breakdown.technical + 0.3 * 0.8,
        2,
    )


def test_confidence_noise_present_uses_noise_score() -> None:
    analysis = AnalysisResult(
        technical=_technical(),
        acoustic=_acoustic(background_noise_present=True, noise_score=0.7),
        speech=_speech(),
    )
    breakdown = WeightedConfidenceEstimator(_settings()).estimate(analysis)
    assert breakdown.acoustic == 0.7


# --- Pipeline integration ------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_uploads_internal_json() -> None:
    storage = FakeStorage()
    settings = _settings()
    pipeline = _pipeline(storage, settings)
    asset = _asset()
    prediction, breakdown, internal = await pipeline.run(asset)

    key = prediction_storage_key(asset.batch_id, asset.id)
    assert key in storage.objects
    stored = json.loads(storage.objects[key].decode("utf-8"))
    assert stored["version"] == "v1.0.0"
    assert set(stored.keys()) == {
        "version",
        "technical",
        "acoustic",
        "speech",
        "confidence",
        "prediction",
    }
    assert set(stored["prediction"].keys()) == set(ASSESSMENT_FIELDS)
    assert stored["confidence"]["overall"] == breakdown.overall
    assert internal is not None
    assert prediction.confidence == breakdown.overall


@pytest.mark.asyncio
async def test_pipeline_internal_disabled() -> None:
    storage = FakeStorage()
    settings = _settings(internal_prediction_enabled=False)
    pipeline = _pipeline(storage, settings)
    _, _, internal = await pipeline.run(_asset())
    assert internal is None
    assert storage.objects == {}


# --- Service: persistence / immutability / regeneration -----------------


@pytest.mark.asyncio
async def test_service_persists_and_idempotent() -> None:
    storage = FakeStorage()
    settings = _settings()
    asset = _asset()
    service = PredictionService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        predictions=FakePredictions(),  # type: ignore[arg-type]
        pipeline=_pipeline(storage, settings),
        settings=settings,
    )
    first = await service.generate_prediction(asset.id)
    objects_before = dict(storage.objects)

    second = await service.generate_prediction(asset.id)
    assert storage.objects == objects_before
    assert second == first


@pytest.mark.asyncio
async def test_service_regeneration() -> None:
    storage = FakeStorage()
    settings = _settings()
    asset = _asset()
    predictions = FakePredictions()
    service = PredictionService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        predictions=predictions,  # type: ignore[arg-type]
        pipeline=_pipeline(storage, settings),
        settings=settings,
    )
    await service.generate_prediction(asset.id)
    first_id = predictions.by_asset[asset.id].prediction_id

    asset.speech_json = _speech(
        emotional_tone=EmotionTone.FRUSTRATED,
        emotional_intensity=EmotionIntensity.HIGH,
        top_probability=0.95,
    ).to_storage_dict()
    regenerated = await service.generate_prediction(asset.id, regenerate=True)
    assert regenerated.emotional_tone is EmotionTone.FRUSTRATED
    assert predictions.by_asset[asset.id].prediction_id != first_id

    # Without regenerate flag the repository refuses to overwrite.
    with pytest.raises(PredictionAlreadyExistsException):
        await predictions.save_engine_result(
            asset.id,
            prediction_version="1.0.0",
            prediction_json=regenerated.to_public_dict(),
            internal_prediction_json=None,
            confidence_breakdown={"overall": 0.9},
            prediction_completed_at=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_service_get_prediction_not_found() -> None:
    settings = _settings()
    service = PredictionService(
        assets=FakeAssets(_asset()),  # type: ignore[arg-type]
        predictions=FakePredictions(),  # type: ignore[arg-type]
        pipeline=_pipeline(FakeStorage(), settings),
        settings=settings,
    )
    with pytest.raises(PredictionNotFoundException):
        await service.get_prediction(uuid4())


# --- Export --------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_csv_and_json_public_fields_only() -> None:
    storage = FakeStorage()
    settings = _settings()
    asset = _asset()
    predictions = FakePredictions()
    service = PredictionService(
        assets=FakeAssets(asset),  # type: ignore[arg-type]
        predictions=predictions,  # type: ignore[arg-type]
        pipeline=_pipeline(storage, settings),
        settings=settings,
    )
    await service.generate_prediction(asset.id)
    record = predictions.by_asset[asset.id]
    record.batch_id = asset.batch_id
    record.audio_asset = asset

    export = PredictionExportService(predictions=predictions)  # type: ignore[arg-type]

    csv_text = await export.export_csv(asset.batch_id)
    import csv as csv_module
    import io as io_module

    rows = list(csv_module.reader(io_module.StringIO(csv_text)))
    assert rows[0] == ["filename", "result_json"]
    assert rows[1][0] == "call.wav"
    result_json = json.loads(rows[1][1])
    assert set(result_json.keys()) == set(ASSESSMENT_FIELDS)

    payload = await export.export_json(asset.batch_id)
    assert payload[0]["filename"] == "call.wav"
    assert set(payload[0]["result"].keys()) == set(ASSESSMENT_FIELDS)
    assert "internal_prediction_json" not in json.dumps(payload)


# --- Factory -------------------------------------------------------------


def test_factory_builds_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.prediction import factory

    monkeypatch.setattr(factory, "CloudflareR2Storage", lambda *args, **kwargs: FakeStorage())
    service = build_prediction_service(session=None)  # type: ignore[arg-type]
    assert isinstance(service, PredictionService)


# --- Validator failure path ----------------------------------------------


def test_validator_raises_on_out_of_bounds_via_construct() -> None:
    class LoosePrediction:
        emotional_tone = None
        emotional_intensity = None
        background_noise_present = True
        background_noise_type = NoiseType.MUSIC
        background_noise_severity = NoiseSeverity.LOW
        confidence = 1.5

        def model_copy(self, update: dict[str, Any]) -> "LoosePrediction":
            return self

    with pytest.raises(PredictionValidationFailedException):
        PredictionValidator().validate(LoosePrediction())  # type: ignore[arg-type]
