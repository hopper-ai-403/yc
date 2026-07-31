"""Repository CRUD tests against Neon PostgreSQL.

These tests require DATABASE_URL / DATABASE_DIRECT_URL to be configured.
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.shared.database.models_registry  # noqa: F401
from app.audio.models import AudioAsset, AudioBatch
from app.audio.repository import (
    SqlAlchemyAudioBatchRepository,
    SqlAlchemyAudioRepository,
)
from app.audit.models import AuditLog
from app.audit.repository import SqlAlchemyAuditRepository
from app.auth.models import User
from app.auth.repository import SqlAlchemyUserRepository
from app.config.settings import get_settings
from app.jobs.models import Job
from app.jobs.repository import SqlAlchemyJobRepository
from app.prediction.models import Prediction
from app.prediction.repository import SqlAlchemyPredictionRepository
from app.shared.domain.enums import (
    AudioQuality,
    AudioStatus,
    BatchStatus,
    EmotionIntensity,
    EmotionTone,
    JobStatus,
    NoiseSeverity,
    UserRole,
)
from app.shared.domain.exceptions import (
    ImmutableEntityException,
    InvariantViolationException,
)
from app.shared.domain.value_objects import (
    ConfidenceScore,
    EmotionResult,
    NoiseResult,
    OverlapResult,
    PredictionResult,
    QualityResult,
    SilenceResult,
)


def _asset_kwargs(
    batch_id: object, filename: str, storage_key: str
) -> dict[str, object]:
    return {
        "batch_id": batch_id,
        "filename": filename,
        "format": "wav",
        "extension": "wav",
        "mime_type": "audio/wav",
        "size_bytes": 128,
        "checksum_sha256": "a" * 64,
        "uploaded_at": datetime.now(timezone.utc),
        "storage_key": storage_key,
        "processing_status": AudioStatus.UPLOADED,
    }


@pytest.fixture(scope="module")
def database_url() -> str:
    get_settings.cache_clear()
    settings = get_settings()
    url = settings.database.migration_url
    if "USER:PASSWORD" in url or "ep-xxx" in url or "localhost" in url:
        pytest.skip("Neon DATABASE_URL not configured")
    return url


@pytest_asyncio.fixture
async def session(database_url: str) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db_session:
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise
        finally:
            await db_session.close()
            await engine.dispose()


@pytest.mark.asyncio
async def test_user_repository_crud(session: AsyncSession) -> None:
    repo = SqlAlchemyUserRepository(session)
    email = f"domain-test-{uuid4().hex}@example.com"
    user = await repo.create(
        User(
            email=email,
            password_hash="hashed-password",  # noqa: S106
            role=UserRole.EVALUATOR,
            is_active=True,
        )
    )
    found = await repo.find_by_email(email)
    assert found is not None
    assert found.id == user.id
    by_id = await repo.find_by_id(user.id)
    assert by_id is not None
    assert by_id.email == email


@pytest.mark.asyncio
async def test_batch_asset_job_prediction_flow(session: AsyncSession) -> None:
    users = SqlAlchemyUserRepository(session)
    batches = SqlAlchemyAudioBatchRepository(session)
    assets = SqlAlchemyAudioRepository(session)
    jobs = SqlAlchemyJobRepository(session)
    predictions = SqlAlchemyPredictionRepository(session)
    audits = SqlAlchemyAuditRepository(session)

    user = await users.create(
        User(
            email=f"batch-owner-{uuid4().hex}@example.com",
            password_hash="hashed",  # noqa: S106
            role=UserRole.ADMIN,
        )
    )
    batch = await batches.create(
        AudioBatch(
            original_filename="calls.zip",
            total_files=1,
            uploaded_by=user.id,
            status=BatchStatus.UPLOADED,
        )
    )
    asset = await assets.create(
        AudioAsset(
            **_asset_kwargs(
                batch.id,
                "call-1.wav",
                f"batches/{batch.id}/{uuid4()}.wav",
            ),
            duration=10.0,
            sample_rate=16000,
            channels=1,
        )
    )
    job = await jobs.create(
        Job(batch_id=batch.id, status=JobStatus.PENDING, progress=0)
    )
    assert job.batch_id == batch.id

    result = PredictionResult(
        emotion=EmotionResult(
            tone=EmotionTone.FRUSTRATED,
            intensity=EmotionIntensity.HIGH,
        ),
        noise=NoiseResult(present=False),
        quality=QualityResult(quality=AudioQuality.SLIGHTLY_IMPAIRED),
        overlap=OverlapResult(present=True),
        silence=SilenceResult(present=False),
        confidence=ConfidenceScore(value=0.77),
    )
    prediction = await predictions.save_from_result(asset.id, result)
    assert prediction.is_persisted is True
    assert prediction.emotional_tone is EmotionTone.FRUSTRATED

    with pytest.raises(ImmutableEntityException):
        await predictions.update(prediction)

    found_batch = await batches.find_by_id(batch.id)
    assert found_batch is not None
    assert len(found_batch.assets) == 1
    found_job = await jobs.find_by_batch(batch.id)
    assert found_job is not None
    assert found_job.id == job.id

    audit = await audits.append(
        AuditLog(
            actor_id=user.id,
            action="BATCH_CREATED",
            resource_type="audio_batch",
            resource_id=batch.id,
            details={"total_files": 1},
        )
    )
    assert audit.id is not None
    logs = await audits.find_by_resource("audio_batch", batch.id)
    assert any(entry.id == audit.id for entry in logs)


@pytest.mark.asyncio
async def test_prediction_rejects_invalid_noise_on_save(
    session: AsyncSession,
) -> None:
    users = SqlAlchemyUserRepository(session)
    batches = SqlAlchemyAudioBatchRepository(session)
    assets = SqlAlchemyAudioRepository(session)
    predictions = SqlAlchemyPredictionRepository(session)

    user = await users.create(
        User(
            email=f"noise-rule-{uuid4().hex}@example.com",
            password_hash="hashed",  # noqa: S106
            role=UserRole.EVALUATOR,
        )
    )
    batch = await batches.create(
        AudioBatch(
            original_filename="n.zip",
            total_files=1,
            uploaded_by=user.id,
        )
    )
    asset = await assets.create(
        AudioAsset(
            **_asset_kwargs(
                batch.id,
                "a.wav",
                f"batches/{batch.id}/{uuid4()}.wav",
            )
        )
    )
    bad = Prediction(
        audio_asset_id=asset.id,
        emotional_tone=EmotionTone.NEUTRAL,
        emotional_intensity=EmotionIntensity.LOW,
        background_noise_present=False,
        background_noise_type="should-be-empty",
        background_noise_severity=NoiseSeverity.NONE,
        audio_quality=AudioQuality.CLEAR,
        speaker_overlap=False,
        long_silence=False,
        confidence=0.5,
    )
    with pytest.raises(InvariantViolationException):
        await predictions.save(bad)
