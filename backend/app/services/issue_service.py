from datetime import datetime, timezone
from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.agreements import Agreement
from app.db.models.complaints import Complaint
from app.db.models.completion import CompletionEvidence
from app.db.models.disputes import Dispute
from app.db.models.enums import AgreementStatus, ComplaintStatus, DisputeStatus, UserRole
from app.db.models.jobs import Job
from app.db.models.payments import Payment
from app.db.models.reviews import Review
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.schemas.issues import (
    AdminResponseRequest,
    ComplaintCreateRequest,
    ComplaintListResponse,
    ComplaintResponse,
    ComplaintStatusRequest,
    DisputeContextResponse,
    DisputeCreateRequest,
    DisputeResolutionRequest,
    DisputeResponse,
    DisputeStatusRequest,
)
from app.db.models.enums import NotificationType
from app.services.notification_service import NotificationService


def _role(session: Session, user_id: UUID) -> str:
    user = session.get(User, user_id)
    return user.role.value if user else "UNKNOWN"


def _complaint_response(session: Session, item: Complaint) -> ComplaintResponse:
    return ComplaintResponse(
        id=item.id, job_id=item.job_id, raised_by=item.raised_by,
        reporter_role=_role(session, item.raised_by), category=item.category,
        message=item.message, status=item.status, resolution=item.resolution,
        created_at=item.created_at, updated_at=item.updated_at,
    )


def _job_participant(session: Session, job: Job, user: User) -> bool:
    consumer = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == job.consumer_id))
    if consumer == user.id:
        return True
    return session.scalar(
        select(WorkerProfile.user_id)
        .join(Agreement, Agreement.worker_id == WorkerProfile.id)
        .where(Agreement.job_id == job.id, Agreement.status == AgreementStatus.ACTIVE, WorkerProfile.user_id == user.id)
    ) is not None


def _job_or_not_found(session: Session, job_id: UUID) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise APIError(404, "Job not found")
    return job


def _job_participant_ids(session: Session, job_id: UUID) -> set[UUID]:
    job = session.get(Job, job_id)
    if job is None:
        return set()
    participants: set[UUID] = set()
    owner = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == job.consumer_id))
    if owner:
        participants.add(owner)
    participants.update(session.scalars(select(WorkerProfile.user_id).join(Agreement, Agreement.worker_id == WorkerProfile.id).where(Agreement.job_id == job_id, Agreement.status == AgreementStatus.ACTIVE)))
    return participants


def create_complaint(session: Session, user: User, data: ComplaintCreateRequest) -> ComplaintResponse:
    if data.job_id is not None:
        job = _job_or_not_found(session, data.job_id)
        if not _job_participant(session, job, user):
            raise APIError(403, "You may only reference jobs you are associated with")
    item = Complaint(raised_by=user.id, **data.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    admins = session.scalars(select(User.id).where(User.role == UserRole.ADMIN)).all()
    service = NotificationService()
    for recipient in admins:
        service.create_notification(
            session, recipient, NotificationType.COMPLAINT_CREATED,
            "Complaint created", "A new complaint requires review.",
            "complaint", item.id, idempotency_key=f"complaint-created:{item.id}",
        )
    session.commit()
    return _complaint_response(session, item)


def my_complaints(session: Session, user: User, page: int, page_size: int) -> ComplaintListResponse:
    predicate = Complaint.raised_by == user.id
    total = session.scalar(select(func.count(Complaint.id)).where(predicate)) or 0
    items = session.scalars(
        select(Complaint).where(predicate).order_by(Complaint.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ComplaintListResponse(items=[_complaint_response(session, item) for item in items], page=page, page_size=page_size, total=total)


def get_complaint(session: Session, user: User, complaint_id: UUID) -> ComplaintResponse:
    item = session.get(Complaint, complaint_id)
    if item is None:
        raise APIError(404, "Complaint not found")
    if user.role is not UserRole.ADMIN and item.raised_by != user.id:
        raise APIError(403, "You may only view your own complaints")
    return _complaint_response(session, item)


def admin_complaints(
    session: Session, status: ComplaintStatus | None, category, reporter_role: UserRole | None,
    job_id: UUID | None, page: int, page_size: int,
) -> ComplaintListResponse:
    statement = select(Complaint)
    predicates = []
    if status:
        predicates.append(Complaint.status == status)
    if category:
        predicates.append(Complaint.category == category)
    if job_id:
        predicates.append(Complaint.job_id == job_id)
    if reporter_role:
        statement = statement.join(User, User.id == Complaint.raised_by)
        predicates.append(User.role == reporter_role)
    if predicates:
        statement = statement.where(*predicates)
    count = select(func.count(Complaint.id)).select_from(Complaint)
    if reporter_role:
        count = count.join(User, User.id == Complaint.raised_by)
    if predicates:
        count = count.where(*predicates)
    total = session.scalar(count) or 0
    items = session.scalars(statement.order_by(Complaint.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return ComplaintListResponse(items=[_complaint_response(session, item) for item in items], page=page, page_size=page_size, total=total)


def update_complaint_status(session: Session, complaint_id: UUID, data: ComplaintStatusRequest) -> ComplaintResponse:
    item = session.get(Complaint, complaint_id)
    if item is None:
        raise APIError(404, "Complaint not found")
    item.status = data.status
    if data.status is ComplaintStatus.RESOLVED:
        item.resolved_at = datetime.now(timezone.utc)
    session.commit()
    NotificationService().create_notification(
        session, item.raised_by, NotificationType.COMPLAINT_STATUS_CHANGED,
        "Complaint status changed", f"Your complaint status is now {item.status.value}.",
        "complaint", item.id, idempotency_key=f"complaint-status:{item.id}:{item.status.value}",
    )
    session.commit()
    return _complaint_response(session, item)


def respond_to_complaint(session: Session, complaint_id: UUID, data: AdminResponseRequest) -> ComplaintResponse:
    item = session.get(Complaint, complaint_id)
    if item is None:
        raise APIError(404, "Complaint not found")
    item.resolution = data.response
    item.status = ComplaintStatus.RESPONDED
    session.commit()
    NotificationService().create_notification(
        session, item.raised_by, NotificationType.COMPLAINT_RESPONSE,
        "Complaint response", "Your complaint received a response from the cooperative.",
        "complaint", item.id, idempotency_key=f"complaint-response:{item.id}",
    )
    session.commit()
    return _complaint_response(session, item)


def create_dispute(session: Session, user: User, job_id: UUID, data: DisputeCreateRequest) -> DisputeResponse:
    job = _job_or_not_found(session, job_id)
    if not _job_participant(session, job, user):
        raise APIError(403, "Only legitimate job participants may raise a dispute")
    item = Dispute(job_id=job_id, raised_by=user.id, category=data.category, description=data.description)
    session.add(item)
    session.commit()
    session.refresh(item)
    service = NotificationService()
    recipients = _job_participant_ids(session, job_id)
    recipients.update(session.scalars(select(User.id).where(User.role == UserRole.ADMIN)))
    for recipient in recipients:
        service.create_notification(session, recipient, NotificationType.DISPUTE_CREATED, "Dispute created", "A dispute was created for a job connected to you.", "dispute", item.id, idempotency_key=f"dispute-created:{item.id}")
    session.commit()
    return _dispute_response(item)


def _dispute_response(item: Dispute) -> DisputeResponse:
    return DisputeResponse(
        id=item.id, job_id=item.job_id, raised_by=item.raised_by, category=item.category,
        description=item.description, status=item.status, resolution=item.resolution,
        created_at=item.created_at, updated_at=item.updated_at,
    )


def admin_disputes(session: Session, status: DisputeStatus | None, job_id: UUID | None, page: int, page_size: int) -> list[DisputeResponse]:
    statement = select(Dispute)
    if status:
        statement = statement.where(Dispute.status == status)
    if job_id:
        statement = statement.where(Dispute.job_id == job_id)
    return [_dispute_response(item) for item in session.scalars(statement.order_by(Dispute.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()]


def dispute_detail(session: Session, user: User, dispute_id: UUID) -> DisputeContextResponse:
    item = session.get(Dispute, dispute_id)
    if item is None:
        raise APIError(404, "Dispute not found")
    job = _job_or_not_found(session, item.job_id)
    if user.role is not UserRole.ADMIN and not (_job_participant(session, job, user) or item.raised_by == user.id):
        raise APIError(403, "You may only view disputes for associated jobs")
    agreements = session.scalars(select(Agreement).where(Agreement.job_id == job.id)).all()
    consumer_id = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == job.consumer_id))
    workers = session.scalars(select(WorkerProfile.user_id).where(WorkerProfile.id.in_([agreement.worker_id for agreement in agreements]))).all() if agreements else []
    payments = session.scalars(select(Payment.status).where(Payment.job_id == job.id)).all()
    evidence = session.scalars(select(CompletionEvidence.id).where(CompletionEvidence.job_id == job.id)).all()
    reviews = session.scalars(select(Review.id).where(Review.job_id == job.id)).all()
    return DisputeContextResponse(
        **_dispute_response(item).model_dump(), job_title=job.title, job_status=job.status.value,
        consumer_id=consumer_id, worker_ids=list(workers), agreement_ids=[agreement.id for agreement in agreements],
        payment_statuses=[status.value for status in payments], completion_evidence_ids=list(evidence), review_ids=list(reviews),
    )


def update_dispute_status(session: Session, dispute_id: UUID, data: DisputeStatusRequest) -> DisputeResponse:
    item = session.get(Dispute, dispute_id)
    if item is None:
        raise APIError(404, "Dispute not found")
    item.status = data.status
    session.commit()
    recipients = _job_participant_ids(session, item.job_id)
    recipients.update(session.scalars(select(User.id).where(User.role == UserRole.ADMIN)))
    for recipient in recipients:
        NotificationService().create_notification(session, recipient, NotificationType.DISPUTE_STATUS_CHANGED, "Dispute status changed", "The status of a dispute connected to your job changed.", "dispute", item.id, idempotency_key=f"dispute-status:{item.id}:{item.status.value}")
    session.commit()
    return _dispute_response(item)


def resolve_dispute(session: Session, dispute_id: UUID, data: DisputeResolutionRequest) -> DisputeResponse:
    item = session.get(Dispute, dispute_id)
    if item is None:
        raise APIError(404, "Dispute not found")
    item.resolution = data.resolution
    item.status = DisputeStatus.RESOLVED
    item.resolved_at = datetime.now(timezone.utc)
    session.commit()
    recipients = _job_participant_ids(session, item.job_id)
    recipients.update(session.scalars(select(User.id).where(User.role == UserRole.ADMIN)))
    for recipient in recipients:
        NotificationService().create_notification(session, recipient, NotificationType.DISPUTE_RESOLVED, "Dispute resolved", "A dispute connected to your job was resolved.", "dispute", item.id, idempotency_key=f"dispute-resolved:{item.id}")
    session.commit()
    return _dispute_response(item)