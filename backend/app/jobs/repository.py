"""Job repository contract and SQLAlchemy implementation."""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.models import Job
from app.shared.domain.enums import JobStatus
from app.shared.domain.exceptions import InvariantViolationException


class JobRepository(ABC):
    """Persistence contract for Job entities."""

    @abstractmethod
    async def create(self, job: Job) -> Job:
        """Persist a new job."""

    @abstractmethod
    async def find_by_id(self, job_id: UUID) -> Job | None:
        """Find a job by id."""

    @abstractmethod
    async def find_by_batch(self, batch_id: UUID) -> Job | None:
        """Find the job owned by a batch."""

    @abstractmethod
    async def find_active(self) -> list[Job]:
        """Return jobs that are pending, queued, or running."""

    @abstractmethod
    async def list_jobs(
        self,
        *,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        """List jobs newest-first with optional status filter."""

    @abstractmethod
    async def update_status(
        self,
        job_id: UUID,
        status: JobStatus,
        *,
        progress: int | None = None,
    ) -> Job | None:
        """Update job status and optional progress."""

    @abstractmethod
    async def save(self, job: Job) -> Job:
        """Persist mutations already applied to a job entity."""


class SqlAlchemyJobRepository(JobRepository):
    """SQLAlchemy-backed JobRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _validate_progress(progress: int) -> None:
        if progress < 0 or progress > 100:
            raise InvariantViolationException(
                "Job progress must be between 0 and 100",
                details={"progress": progress},
            )

    async def create(self, job: Job) -> Job:
        self._validate_progress(job.progress)
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def find_by_id(self, job_id: UUID) -> Job | None:
        return await self._session.get(Job, job_id)

    async def find_by_batch(self, batch_id: UUID) -> Job | None:
        statement = select(Job).where(Job.batch_id == batch_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def find_active(self) -> list[Job]:
        statement = select(Job).where(
            Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING])
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def list_jobs(
        self,
        *,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        statement = select(Job).order_by(Job.created_at.desc())
        if status is not None:
            statement = statement.where(Job.status == status)
        statement = statement.offset(offset).limit(limit)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def update_status(
        self,
        job_id: UUID,
        status: JobStatus,
        *,
        progress: int | None = None,
    ) -> Job | None:
        job = await self.find_by_id(job_id)
        if job is None:
            return None
        job.status = status
        if progress is not None:
            self._validate_progress(progress)
            job.progress = progress
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def save(self, job: Job) -> Job:
        self._validate_progress(job.progress)
        await self._session.flush()
        await self._session.refresh(job)
        return job
