from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.db.models.agreements import Agreement
from app.db.models.enums import JobStatus, UserRole
from app.db.models.jobs import Job, JobImage, JobRequirement
from app.db.models.skills import Skill
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.schemas.jobs import JobCreateRequest, JobListQuery, JobResponse, JobUpdateRequest, PaginatedJobsResponse, SkillResponse
from app.services.location_intelligence_service import resolve_location


ALLOWED_IMAGE_BUCKETS = {"job-images", "approved-media"}


def _job_query():
    return select(Job).options(
        selectinload(Job.requirements).selectinload(JobRequirement.skill),
        selectinload(Job.images),
    )


def _job_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        category=job.category,
        title=job.title,
        description=job.description,
        location=job.location,
        latitude=float(job.latitude) if job.latitude is not None else None,
        longitude=float(job.longitude) if job.longitude is not None else None,
        required_worker_count=job.required_worker_count,
        minimum_platform_cost=job.minimum_platform_cost,
        emergency_level=job.emergency_level,
        scheduled_date=job.scheduled_date,
        start_time=job.start_time,
        end_time=job.end_time,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        required_skills=[SkillResponse(id=item.skill.id, name=item.skill.name) for item in job.requirements],
        images=[
            {"id": image.id, "storage_bucket": image.storage_bucket, "storage_path": image.storage_path}
            for image in job.images
        ],
    )


def create_job(session: Session, user: User, data: JobCreateRequest) -> JobResponse:
    consumer_profile = session.scalar(select(ConsumerProfile).where(ConsumerProfile.user_id == user.id))
    if consumer_profile is None:
        raise APIError(409, "Consumer profile is not available")

    skills = []
    if data.required_skill_ids:
        skills = list(session.scalars(select(Skill).where(Skill.id.in_(data.required_skill_ids))))
        if len(skills) != len(data.required_skill_ids):
            raise APIError(422, "One or more required skills do not exist")

    invalid_bucket = next((image.storage_bucket for image in data.images if image.storage_bucket not in ALLOWED_IMAGE_BUCKETS), None)
    if invalid_bucket:
        raise APIError(422, "Unsupported Storage bucket for job image metadata")

    coordinates = resolve_location(data.location)
    job = Job(
        consumer_id=consumer_profile.id,
        category=data.category,
        title=data.title,
        description=data.description,
        location=data.location,
        latitude=coordinates[0] if coordinates else None,
        longitude=coordinates[1] if coordinates else None,
        required_worker_count=data.required_worker_count,
        minimum_platform_cost=data.minimum_platform_cost,
        emergency_level=data.emergency_level,
        scheduled_date=data.scheduled_date,
        start_time=data.start_time,
        end_time=data.end_time,
        status=JobStatus.POSTED,
    )
    session.add(job)
    session.flush()
    for skill in skills:
        session.add(JobRequirement(job_id=job.id, skill_id=skill.id, worker_count=1))
    for image in data.images:
        session.add(
            JobImage(
                job_id=job.id,
                uploaded_by=user.id,
                storage_bucket=image.storage_bucket,
                storage_path=image.storage_path,
            )
        )
    session.commit()
    session.refresh(job)
    return _job_response(session.scalar(_job_query().where(Job.id == job.id)))


def get_job(session: Session, user: User, job_id: UUID) -> JobResponse:
    job = session.scalar(_job_query().where(Job.id == job_id))
    if job is None:
        raise APIError(404, "Job not found")
    if user.role is UserRole.ADMIN:
        return _job_response(job)
    owner_id = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == job.consumer_id))
    if owner_id == user.id:
        return _job_response(job)
    if user.role is UserRole.WORKER and job.status in {JobStatus.POSTED, JobStatus.APPLICATIONS}:
        return _job_response(job)
    participant = session.scalar(
        select(WorkerProfile.user_id)
        .join(Agreement, Agreement.worker_id == WorkerProfile.id)
        .where(Agreement.job_id == job.id, WorkerProfile.user_id == user.id)
    )
    if participant is None:
        raise APIError(403, "You are not authorized to view this job")
    return _job_response(job)


def update_job(session: Session, user: User, job_id: UUID, data: JobUpdateRequest) -> JobResponse:
    consumer_profile = session.scalar(select(ConsumerProfile).where(ConsumerProfile.user_id == user.id))
    job = session.scalar(_job_query().where(Job.id == job_id))
    if job is None:
        raise APIError(404, "Job not found")
    if consumer_profile is None or job.consumer_id != consumer_profile.id:
        raise APIError(403, "You may only modify jobs you own")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    if "location" in data.model_dump(exclude_unset=True):
        coordinates = resolve_location(job.location)
        job.latitude, job.longitude = coordinates or (None, None)
    if job.start_time is not None and job.end_time is not None and job.end_time <= job.start_time:
        raise APIError(422, "end_time must be after start_time")
    session.commit()
    session.refresh(job)
    return _job_response(session.scalar(_job_query().where(Job.id == job.id)))


def list_jobs(session: Session, user: User, query: JobListQuery) -> PaginatedJobsResponse:
    statement = _job_query()
    count_statement = select(func.count()).select_from(Job)
    if user.role.value == "WORKER":
        statement = statement.where(Job.status.in_([JobStatus.POSTED, JobStatus.APPLICATIONS]))
        count_statement = count_statement.where(Job.status.in_([JobStatus.POSTED, JobStatus.APPLICATIONS]))
    elif user.role.value == "CONSUMER":
        profile = session.scalar(select(ConsumerProfile).where(ConsumerProfile.user_id == user.id))
        if profile is None:
            raise APIError(409, "Consumer profile is not available")
        statement = statement.where(Job.consumer_id == profile.id)
        count_statement = count_statement.where(Job.consumer_id == profile.id)

    if query.category:
        statement = statement.where(Job.category == query.category)
        count_statement = count_statement.where(Job.category == query.category)
    if query.emergency_level:
        statement = statement.where(Job.emergency_level == query.emergency_level)
        count_statement = count_statement.where(Job.emergency_level == query.emergency_level)
    if query.scheduled_date:
        statement = statement.where(Job.scheduled_date == query.scheduled_date)
        count_statement = count_statement.where(Job.scheduled_date == query.scheduled_date)
    if query.location:
        statement = statement.where(Job.location.ilike(f"%{query.location}%"))
        count_statement = count_statement.where(Job.location.ilike(f"%{query.location}%"))
    if query.min_price is not None:
        statement = statement.where(Job.minimum_platform_cost >= query.min_price)
        count_statement = count_statement.where(Job.minimum_platform_cost >= query.min_price)
    if query.max_price is not None:
        statement = statement.where(Job.minimum_platform_cost <= query.max_price)
        count_statement = count_statement.where(Job.minimum_platform_cost <= query.max_price)
    if query.required_worker_count is not None:
        statement = statement.where(Job.required_worker_count == query.required_worker_count)
        count_statement = count_statement.where(Job.required_worker_count == query.required_worker_count)
    if query.status and user.role.value != "WORKER":
        statement = statement.where(Job.status == query.status)
        count_statement = count_statement.where(Job.status == query.status)

    total = session.scalar(count_statement) or 0
    jobs = session.scalars(statement.order_by(Job.created_at.desc()).offset((query.page - 1) * query.page_size).limit(query.page_size)).all()
    return PaginatedJobsResponse(
        items=[_job_response(job) for job in jobs],
        page=query.page,
        page_size=query.page_size,
        total=total,
        pages=ceil(total / query.page_size) if total else 0,
    )