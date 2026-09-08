from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_consumer, require_worker
from app.db.models.users import User
from app.db.session import get_db
from app.schemas.scheduling import AvailabilityCreateRequest, AvailabilityResponse, JobScheduleResponse, ScheduleResponse
from app.services.scheduling_service import (
    create_availability,
    delete_availability,
    job_schedule,
    list_availability,
    update_availability,
    worker_schedule,
)


router = APIRouter(tags=["scheduling"])


@router.post("/workers/me/availability", response_model=AvailabilityResponse, status_code=status.HTTP_201_CREATED)
def create_worker_availability(
    data: AvailabilityCreateRequest,
    user: User = Depends(require_worker),
    session: Session = Depends(get_db),
) -> AvailabilityResponse:
    return create_availability(session, user, data)


@router.get("/workers/me/availability", response_model=list[AvailabilityResponse])
def get_worker_availability(
    user: User = Depends(require_worker), session: Session = Depends(get_db)
) -> list[AvailabilityResponse]:
    return list_availability(session, user)


@router.patch("/workers/me/availability/{availability_id}", response_model=AvailabilityResponse)
def patch_worker_availability(
    availability_id: UUID,
    data: AvailabilityCreateRequest,
    user: User = Depends(require_worker),
    session: Session = Depends(get_db),
) -> AvailabilityResponse:
    return update_availability(session, user, availability_id, data)


@router.delete("/workers/me/availability/{availability_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_worker_availability(
    availability_id: UUID,
    user: User = Depends(require_worker),
    session: Session = Depends(get_db),
) -> Response:
    delete_availability(session, user, availability_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/workers/me/schedule", response_model=list[ScheduleResponse])
def get_worker_schedule(
    user: User = Depends(require_worker), session: Session = Depends(get_db)
) -> list[ScheduleResponse]:
    return worker_schedule(session, user)


@router.get("/workers/me/upcoming-jobs", response_model=list[ScheduleResponse])
def get_worker_upcoming_jobs(
    user: User = Depends(require_worker), session: Session = Depends(get_db)
) -> list[ScheduleResponse]:
    return worker_schedule(session, user, upcoming=True)


@router.get("/jobs/{job_id}/schedule", response_model=list[JobScheduleResponse])
def get_job_schedule(
    job_id: UUID,
    user: User = Depends(require_consumer),
    session: Session = Depends(get_db),
) -> list[JobScheduleResponse]:
    return job_schedule(session, user, job_id)