from datetime import date, time
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.db.models.agreements import Agreement
from app.db.models.availability import WorkerAvailability
from app.db.models.enums import AgreementStatus, AvailabilityStatus
from app.db.models.jobs import Job
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.schemas.scheduling import (
    AvailabilityCreateRequest,
    AvailabilityResponse,
    JobScheduleResponse,
    ScheduleResponse,
)


def _worker_profile(session: Session, user: User) -> WorkerProfile:
    profile = session.scalar(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    if profile is None:
        raise APIError(409, "Worker profile is not available")
    return profile


def _availability_response(item: WorkerAvailability) -> AvailabilityResponse:
    return AvailabilityResponse.model_validate(item)


def _overlap_clause(start_time: time, end_time: time):
    return and_(Agreement.start_time < end_time, Agreement.end_time > start_time)


def validate_worker_schedule(
    session: Session,
    worker_id: UUID,
    scheduled_date: date,
    start_time: time,
    end_time: time,
) -> None:
    if end_time <= start_time:
        raise APIError(422, "Agreement end time must be after start time")

    windows = session.scalars(
        select(WorkerAvailability).where(
            WorkerAvailability.worker_id == worker_id,
            WorkerAvailability.available_date == scheduled_date,
        )
    ).all()
    available_windows = [window for window in windows if window.status is AvailabilityStatus.AVAILABLE]
    if windows and not any(window.start_time <= start_time and window.end_time >= end_time for window in available_windows):
        raise APIError(409, "Worker is not available for the agreed time")

    conflict = session.scalar(
        select(Agreement.id).where(
            Agreement.worker_id == worker_id,
            Agreement.status.in_([AgreementStatus.PENDING, AgreementStatus.ACTIVE]),
            Agreement.agreed_date == scheduled_date,
            _overlap_clause(start_time, end_time),
        ).with_for_update()
    )
    if conflict is not None:
        raise APIError(409, "Worker already has an overlapping scheduled agreement")


def create_availability(session: Session, user: User, data: AvailabilityCreateRequest) -> AvailabilityResponse:
    worker = _worker_profile(session, user)
    conflict = session.scalar(
        select(WorkerAvailability.id).where(
            WorkerAvailability.worker_id == worker.id,
            WorkerAvailability.available_date == data.available_date,
            WorkerAvailability.start_time < data.end_time,
            WorkerAvailability.end_time > data.start_time,
        )
    )
    if conflict is not None:
        raise APIError(409, "Availability window overlaps an existing window")
    item = WorkerAvailability(worker_id=worker.id, **data.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return _availability_response(item)


def list_availability(session: Session, user: User) -> list[AvailabilityResponse]:
    worker = _worker_profile(session, user)
    items = session.scalars(
        select(WorkerAvailability)
        .where(WorkerAvailability.worker_id == worker.id)
        .order_by(WorkerAvailability.available_date, WorkerAvailability.start_time)
    ).all()
    return [_availability_response(item) for item in items]


def update_availability(session: Session, user: User, availability_id: UUID, data: AvailabilityCreateRequest) -> AvailabilityResponse:
    worker = _worker_profile(session, user)
    item = session.scalar(select(WorkerAvailability).where(WorkerAvailability.id == availability_id))
    if item is None:
        raise APIError(404, "Availability window not found")
    if item.worker_id != worker.id:
        raise APIError(403, "You may only modify your own availability")
    conflict = session.scalar(
        select(WorkerAvailability.id).where(
            WorkerAvailability.id != availability_id,
            WorkerAvailability.worker_id == worker.id,
            WorkerAvailability.available_date == data.available_date,
            WorkerAvailability.start_time < data.end_time,
            WorkerAvailability.end_time > data.start_time,
        )
    )
    if conflict is not None:
        raise APIError(409, "Availability window overlaps an existing window")
    for field, value in data.model_dump().items():
        setattr(item, field, value)
    session.commit()
    session.refresh(item)
    return _availability_response(item)


def delete_availability(session: Session, user: User, availability_id: UUID) -> None:
    worker = _worker_profile(session, user)
    item = session.scalar(select(WorkerAvailability).where(WorkerAvailability.id == availability_id))
    if item is None:
        raise APIError(404, "Availability window not found")
    if item.worker_id != worker.id:
        raise APIError(403, "You may only modify your own availability")
    session.delete(item)
    session.commit()


def worker_schedule(session: Session, user: User, upcoming: bool = False) -> list[ScheduleResponse]:
    worker = _worker_profile(session, user)
    statement = (
        select(Agreement)
        .join(Job, Agreement.job_id == Job.id)
        .where(
            Agreement.worker_id == worker.id,
            Agreement.status.in_([AgreementStatus.PENDING, AgreementStatus.ACTIVE]),
        )
        .options(selectinload(Agreement.job))
        .order_by(Agreement.agreed_date, Agreement.start_time)
    )
    if upcoming:
        statement = statement.where(Agreement.agreed_date >= date.today())
    return [
        ScheduleResponse(
            agreement_id=item.id,
            job_id=item.job_id,
            job_title=item.job.title,
            job_category=item.job.category,
            scheduled_date=item.agreed_date,
            start_time=item.start_time,
            end_time=item.end_time,
            status=item.status,
        )
        for item in session.scalars(statement).all()
    ]


def job_schedule(session: Session, user: User, job_id: UUID) -> list[JobScheduleResponse]:
    owns_job = session.scalar(
        select(Job.id).join(ConsumerProfile, Job.consumer_id == ConsumerProfile.id).where(
            Job.id == job_id, ConsumerProfile.user_id == user.id
        )
    )
    if owns_job is None:
        raise APIError(404, "Job schedule not found")
    items = session.scalars(
        select(Agreement)
        .where(Agreement.job_id == job_id, Agreement.status.in_([AgreementStatus.PENDING, AgreementStatus.ACTIVE]))
        .options(selectinload(Agreement.worker).selectinload(WorkerProfile.user))
    ).all()
    return [
        JobScheduleResponse(
            agreement_id=item.id,
            job_id=item.job_id,
            worker_id=item.worker_id,
            worker_name=item.worker.user.name,
            scheduled_date=item.agreed_date,
            start_time=item.start_time,
            end_time=item.end_time,
            status=item.status,
        )
        for item in items
    ]