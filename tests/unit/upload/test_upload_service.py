"""Upload service and API tests."""

from collections.abc import AsyncGenerator
from io import BytesIO
from unittest.mock import AsyncMock
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.shared.database.models_registry  # noqa: F401
from app.audio.repository import (
    SqlAlchemyAudioBatchRepository,
    SqlAlchemyAudioRepository,
)
from app.auth.repository import SqlAlchemyUserRepository
from app.config.settings import UploadSettings, get_settings
from app.jobs.models import Job
from app.jobs.repository import SqlAlchemyJobRepository
from app.main import create_application
from app.shared.domain.enums import JobStatus
from app.upload.exceptions import EmptyUploadException
from app.upload.service import IncomingUpload, UploadService


class FakeJobService:
    """Persists PENDING jobs then marks them QUEUED without Celery."""

    def __init__(self, session: AsyncSession) -> None:
        self._jobs = SqlAlchemyJobRepository(session)
        self._batches = SqlAlchemyAudioBatchRepository(session)
        self.queue_calls = 0

    async def create_job(self, batch_id: UUID) -> Job:
        existing = await self._jobs.find_by_batch(batch_id)
        if existing is not None:
            return existing
        batch = await self._batches.find_by_id(batch_id)
        assert batch is not None
        return await self._jobs.create(
            Job(
                batch_id=batch_id,
                status=JobStatus.PENDING,
                progress=0,
                total_files=batch.total_files,
                processed_files=0,
                failed_files=0,
            )
        )

    async def queue_job(self, job_id: UUID, *, countdown: int = 0) -> Job:
        del countdown
        self.queue_calls += 1
        job = await self._jobs.find_by_id(job_id)
        assert job is not None
        job.status = JobStatus.QUEUED
        return await self._jobs.save(job)


class FakeStorage:
    """In-memory StorageProvider stand-in for upload tests."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload_file(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        del content_type, metadata
        self.objects[key] = data
        return key

    async def delete_file(self, key: str) -> None:
        self.objects.pop(key, None)

    async def upload(self, *args: object, **kwargs: object) -> str:
        raise NotImplementedError

    async def download(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        await self.delete_file(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def list(self, prefix: str = "", *, max_keys: int = 1000) -> list[str]:
        del max_keys
        return [key for key in self.objects if key.startswith(prefix)]

    async def generate_signed_url(self, key: str, **kwargs: object) -> str:
        del kwargs
        return f"https://example.test/{key}"

    async def health_check(self) -> bool:
        return True


@pytest.fixture(scope="module")
def database_url() -> str:
    get_settings.cache_clear()
    settings = get_settings()
    url = settings.database.migration_url
    if "USER:PASSWORD" in url or "ep-xxx" in url:
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


@pytest_asyncio.fixture
async def upload_service(session: AsyncSession) -> UploadService:
    return UploadService(
        settings=UploadSettings(
            system_uploader_email=f"uploader-{uuid4().hex}@test.local"
        ),
        storage=FakeStorage(),  # type: ignore[arg-type]
        users=SqlAlchemyUserRepository(session),
        batches=SqlAlchemyAudioBatchRepository(session),
        assets=SqlAlchemyAudioRepository(session),
        job_service=FakeJobService(session),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_single_file_upload(upload_service: UploadService) -> None:
    result = await upload_service.upload(
        [
            IncomingUpload(
                filename="call.wav",
                content=b"RIFF....WAVE",
                content_type="audio/wav",
            )
        ]
    )
    assert result.files_uploaded == 1
    assert result.files_rejected == 0
    assert result.job_id


@pytest.mark.asyncio
async def test_zip_upload(upload_service: UploadService) -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("one.wav", b"RIFFWAV1")
        archive.writestr("two.mp3", b"ID3AUDIO")
        archive.writestr("notes.txt", b"nope")
    result = await upload_service.upload(
        [
            IncomingUpload(
                filename="batch.zip",
                content=buffer.getvalue(),
                content_type="application/zip",
            )
        ]
    )
    assert result.files_uploaded == 2
    assert result.files_rejected >= 1


@pytest.mark.asyncio
async def test_invalid_file_upload(upload_service: UploadService) -> None:
    with pytest.raises(EmptyUploadException):
        await upload_service.upload(
            [
                IncomingUpload(
                    filename="readme.txt",
                    content=b"hello",
                    content_type="text/plain",
                )
            ]
        )


@pytest.mark.asyncio
async def test_duplicate_file_upload(upload_service: UploadService) -> None:
    from app.upload.exceptions import DuplicateFilenameException

    with pytest.raises(DuplicateFilenameException):
        await upload_service.upload(
            [
                IncomingUpload(
                    filename="same.wav",
                    content=b"RIFFA",
                    content_type="audio/wav",
                ),
                IncomingUpload(
                    filename="same.wav",
                    content=b"RIFFB",
                    content_type="audio/wav",
                ),
            ]
        )


@pytest.mark.asyncio
async def test_corrupted_zip_upload(upload_service: UploadService) -> None:
    from app.upload.exceptions import CorruptedArchiveException

    with pytest.raises(CorruptedArchiveException):
        await upload_service.upload(
            [
                IncomingUpload(
                    filename="broken.zip",
                    content=b"not-zip",
                    content_type="application/zip",
                )
            ]
        )


@pytest.mark.asyncio
async def test_r2_upload_keys(upload_service: UploadService) -> None:
    storage = FakeStorage()
    service = UploadService(
        settings=upload_service._settings,
        storage=storage,  # type: ignore[arg-type]
        users=upload_service._users,
        batches=upload_service._batches,
        assets=upload_service._assets,
        job_service=upload_service._job_service,
    )
    result = await service.upload(
        [
            IncomingUpload(
                filename="stored.ogg",
                content=b"OggS....",
                content_type="audio/ogg",
            )
        ]
    )
    assert any(
        key.startswith(f"uploads/{result.batch_id}/original/")
        for key in storage.objects
    )


def test_upload_api_endpoint_with_mocked_service() -> None:
    from unittest.mock import patch

    from app.infrastructure.redis.client import get_redis_client
    from app.upload.dependencies import get_upload_service

    get_settings.cache_clear()
    get_redis_client.cache_clear()
    application = create_application()

    async def fake_upload(uploads: list[IncomingUpload]) -> object:
        del uploads
        from app.upload.schemas import UploadResultData

        return UploadResultData(
            batch_id=uuid4(),
            job_id=uuid4(),
            files_uploaded=1,
            files_rejected=0,
        )

    mock_service = AsyncMock()
    mock_service.upload = AsyncMock(side_effect=fake_upload)
    application.dependency_overrides[get_upload_service] = lambda: mock_service

    redis_mock = AsyncMock()
    redis_mock.connect = AsyncMock()
    redis_mock.disconnect = AsyncMock()

    with patch("app.main.get_redis_client", return_value=redis_mock):
        with TestClient(application) as client:
            response = client.post(
                "/api/v1/uploads",
                files=[("files", ("demo.wav", b"RIFFDATA", "audio/wav"))],
            )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["files_uploaded"] == 1
    application.dependency_overrides.clear()
    get_settings.cache_clear()
    get_redis_client.cache_clear()
