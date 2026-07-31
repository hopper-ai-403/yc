"""Jobs HTTP API.

Routes orchestrate dependency-injected JobService only.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.jobs.dependencies import get_job_service
from app.jobs.schemas import (
    JobActionData,
    JobListData,
    JobProgressData,
    JobRead,
    StartJobData,
)
from app.jobs.service import JobService
from app.shared.domain.enums import JobStatus
from app.shared.response.schemas import SuccessResponse

router = APIRouter(prefix="/api/v1", tags=["Jobs"])


@router.post(
    "/jobs/{job_id}/start",
    response_model=SuccessResponse[StartJobData],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a job for asynchronous processing",
)
async def start_job(
    job_id: UUID,
    service: JobService = Depends(get_job_service),
) -> SuccessResponse[StartJobData]:
    job = await service.queue_job(job_id)
    return SuccessResponse(
        message="Job queued for processing",
        data=StartJobData(job=JobRead.from_entity(job), queued=True),
    )


@router.post(
    "/jobs/{job_id}/retry",
    response_model=SuccessResponse[JobActionData],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry failed audio assets for a job",
)
async def retry_job(
    job_id: UUID,
    service: JobService = Depends(get_job_service),
) -> SuccessResponse[JobActionData]:
    job = await service.retry_job(job_id)
    return SuccessResponse(
        message="Job retry queued",
        data=JobActionData(
            job=JobRead.from_entity(job),
            detail={"retry_count": job.retry_count},
        ),
    )


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=SuccessResponse[JobActionData],
    summary="Cancel a job",
)
async def cancel_job(
    job_id: UUID,
    service: JobService = Depends(get_job_service),
) -> SuccessResponse[JobActionData]:
    job = await service.cancel_job(job_id)
    return SuccessResponse(
        message="Job cancelled",
        data=JobActionData(job=JobRead.from_entity(job)),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=SuccessResponse[JobRead],
    summary="Get job details",
)
async def get_job(
    job_id: UUID,
    service: JobService = Depends(get_job_service),
) -> SuccessResponse[JobRead]:
    job = await service.get_job(job_id)
    return SuccessResponse(message="Job retrieved", data=job)


@router.get(
    "/jobs/{job_id}/progress",
    response_model=SuccessResponse[JobProgressData],
    summary="Get job progress (Redis-cached with DB fallback)",
)
async def get_job_progress(
    job_id: UUID,
    service: JobService = Depends(get_job_service),
) -> SuccessResponse[JobProgressData]:
    progress = await service.get_progress(job_id)
    return SuccessResponse(message="Job progress retrieved", data=progress)


@router.get(
    "/jobs",
    response_model=SuccessResponse[JobListData],
    summary="List jobs",
)
async def list_jobs(
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: JobService = Depends(get_job_service),
) -> SuccessResponse[JobListData]:
    items = await service.list_jobs(
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(
        message="Jobs listed",
        data=JobListData(items=items, count=len(items)),
    )
