from decimal import Decimal
from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.agreements import Agreement
from app.db.models.enums import AgreementStatus, JobStatus, UserRole
from app.db.models.jobs import Job
from app.db.models.reviews import Review
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.schemas.reviews import ReputationResponse, ReviewCreateRequest, ReviewListResponse, ReviewResponse
from app.db.models.enums import NotificationType
from app.services.notification_service import NotificationService
from app.realtime.events import RealtimeEvent
from app.realtime.models import RealtimeResourceScope, RealtimeSubject
from app.realtime.service import RealtimeDelivery, build_event


def _response(item: Review) -> ReviewResponse:
    return ReviewResponse(
        id=item.id,
        job_id=item.job_id,
        reviewer_id=item.reviewer_id,
        reviewed_user_id=item.reviewed_user_id,
        rating=item.rating,
        comment=item.comment,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _job_or_404(session: Session, job_id: UUID) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise APIError(404, "Job not found")
    return job


def _consumer_id(session: Session, job: Job) -> UUID | None:
    return session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == job.consumer_id))


def _worker_ids(session: Session, job_id: UUID) -> set[UUID]:
    worker_user_ids = session.scalars(
        select(WorkerProfile.user_id)
        .join(Agreement, Agreement.worker_id == WorkerProfile.id)
        .where(Agreement.job_id == job_id, Agreement.status == AgreementStatus.ACTIVE)
    )
    return set(worker_user_ids)


def _is_participant(session: Session, job: Job, user_id: UUID) -> bool:
    return user_id == _consumer_id(session, job) or user_id in _worker_ids(session, job.id)


def _is_valid_pair(session: Session, job: Job, reviewer_id: UUID, reviewed_id: UUID) -> bool:
    consumer_id = _consumer_id(session, job)
    workers = _worker_ids(session, job.id)
    return (reviewer_id == consumer_id and reviewed_id in workers) or (
        reviewer_id in workers and reviewed_id == consumer_id
    )


def create_review(session: Session, user: User, job_id: UUID, data: ReviewCreateRequest) -> ReviewResponse:
    job = _job_or_404(session, job_id)
    if job.status is not JobStatus.COMPLETED:
        raise APIError(409, "Reviews are available only after successful completion")
    if data.reviewed_user_id == user.id:
        raise APIError(422, "Users cannot review themselves")
    if not _is_valid_pair(session, job, user.id, data.reviewed_user_id):
        raise APIError(403, "You may only review a legitimate participant in this job")
    existing = session.scalar(
        select(Review).where(
            Review.job_id == job_id,
            Review.reviewer_id == user.id,
            Review.reviewed_user_id == data.reviewed_user_id,
        )
    )
    if existing is not None:
        raise APIError(409, "Review already exists")
    item = Review(
        job_id=job_id,
        reviewer_id=user.id,
        reviewed_user_id=data.reviewed_user_id,
        rating=data.rating,
        comment=data.comment.strip() if data.comment is not None else None,
    )
    session.add(item)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise APIError(409, "Review already exists") from error
    session.refresh(item)
    NotificationService().create_notification(session, data.reviewed_user_id, NotificationType.REVIEW_AVAILABLE, "Review available", "A completed job has a new review available.", "job", job_id, idempotency_key=f"review-available:{item.id}")
    NotificationService().create_notification(session, user.id, NotificationType.REVIEW_CREATED, "Review created", "Your review was recorded for the completed job.", "review", item.id, idempotency_key=f"review-created:{item.id}")
    session.commit()
    consumer_id = _consumer_id(session, job)
    worker_ids = _worker_ids(session, job.id)
    subjects = [RealtimeSubject(consumer_id, UserRole.CONSUMER)] if consumer_id else []
    subjects.extend(RealtimeSubject(worker_id, UserRole.WORKER) for worker_id in worker_ids)
    RealtimeDelivery().publish(build_event(
        RealtimeEvent.REVIEW_CREATED,
        {"review_id": item.id, "job_id": job_id, "reviewed_user_id": data.reviewed_user_id, "rating": data.rating},
        subjects,
        RealtimeResourceScope(participant_user_ids=frozenset({consumer_id, *worker_ids} - {None})),
        correlation_id=str(item.id),
    ))
    return _response(item)


def list_job_reviews(session: Session, user: User, job_id: UUID) -> list[ReviewResponse]:
    job = _job_or_404(session, job_id)
    if user.role is not UserRole.ADMIN and not _is_participant(session, job, user.id):
        raise APIError(403, "You may only view reviews for a job you participated in")
    return [
        _response(item)
        for item in session.scalars(select(Review).where(Review.job_id == job_id).order_by(Review.created_at)).all()
    ]


def reputation(session: Session, user_id: UUID) -> ReputationResponse:
    if session.get(User, user_id) is None:
        raise APIError(404, "User not found")
    reviews = session.scalars(
        select(Review).where(Review.reviewed_user_id == user_id).order_by(Review.created_at.desc())
    ).all()
    distribution = {str(rating): 0 for rating in range(1, 6)}
    for item in reviews:
        distribution[str(item.rating)] += 1
    average = float(Decimal(sum(item.rating for item in reviews)) / Decimal(len(reviews))) if reviews else None
    return ReputationResponse(
        user_id=user_id,
        average_rating=average,
        total_reviews=len(reviews),
        rating_distribution=distribution,
        reviews=[_response(item) for item in reviews],
    )


def my_reviews(session: Session, user: User, page: int, page_size: int) -> ReviewListResponse:
    total = session.scalar(select(func.count(Review.id)).where(Review.reviewer_id == user.id)) or 0
    items = session.scalars(
        select(Review)
        .where(Review.reviewer_id == user.id)
        .order_by(Review.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ReviewListResponse(
        items=[_response(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )