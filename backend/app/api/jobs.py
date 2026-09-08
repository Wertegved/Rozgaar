from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_consumer
from app.db.models.enums import EmergencyLevel, JobStatus
from app.db.models.users import User
from app.db.session import get_db
from app.schemas.jobs import JobCreateRequest, JobListQuery, JobResponse, JobUpdateRequest, PaginatedJobsResponse
from app.services.job_service import create_job, get_job, list_jobs, update_job


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create(
    data: JobCreateRequest,
    user: User = Depends(require_consumer),
    session: Session = Depends(get_db),
) -> JobResponse:
    return create_job(session, user, data)


@router.get("", response_model=PaginatedJobsResponse)
def list_discoverable(
    category: str | None = Query(default=None),
    emergency_level: EmergencyLevel | None = Query(default=None),
    scheduled_date: date | None = Query(default=None),
    location: str | None = Query(default=None),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    required_worker_count: int | None = Query(default=None, gt=0),
    job_status: JobStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PaginatedJobsResponse:
    query = JobListQuery(
        category=category,
        emergency_level=emergency_level,
        scheduled_date=scheduled_date,
        location=location,
        min_price=min_price,
        max_price=max_price,
        required_worker_count=required_worker_count,
        status=job_status,
        page=page,
        page_size=page_size,
    )
    return list_jobs(session, user, query)


@router.get("/{job_id}", response_model=JobResponse)
def detail(
    job_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> JobResponse:
    return get_job(session, user, job_id)


@router.patch("/{job_id}", response_model=JobResponse)
def update(
    job_id: UUID,
    data: JobUpdateRequest,
    user: User = Depends(require_consumer),
    session: Session = Depends(get_db),
) -> JobResponse:
    return update_job(session, user, job_id, data)