from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.db.models.agreements import Agreement
from app.db.models.applications import Application
from app.db.models.enums import AgreementStatus, ApplicationStatus, JobStatus, NegotiationStatus
from app.db.models.jobs import Job
from app.db.models.negotiations import Negotiation
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.schemas.applications import (
    AgreementResponse,
    ApplicantResponse,
    ApplicationCreateRequest,
    ApplicationResponse,
    CounterOfferRequest,
    NegotiationResponse,
)
from app.services.scheduling_service import validate_worker_schedule
from app.db.models.enums import NotificationType
from app.services.notification_service import NotificationService


def _negotiation_response(item: Negotiation) -> NegotiationResponse:
    return NegotiationResponse(
        id=item.id,
        proposed_amount=item.proposed_amount,
        status=item.status,
        initiated_by=item.initiated_by,
        message=item.message,
        created_at=item.created_at,
    )


def _application_response(item: Application) -> ApplicationResponse:
    return ApplicationResponse(
        id=item.id,
        job_id=item.job_id,
        worker_id=item.worker_id,
        proposed_price=item.proposed_price,
        status=item.status,
        submitted_at=item.submitted_at,
        withdrawn_at=item.withdrawn_at,
        job_title=item.job.title,
        job_category=item.job.category,
        job_location=item.job.location,
        job_description=item.job.description,
        scheduled_date=item.job.scheduled_date,
        start_time=item.job.start_time,
        end_time=item.job.end_time,
        required_worker_count=item.job.required_worker_count,
        emergency_level=item.job.emergency_level,
        minimum_platform_cost=item.job.minimum_platform_cost,
        negotiations=[_negotiation_response(item) for item in item.negotiations],
    )


def _load_application(session: Session, application_id: UUID) -> Application:
    item = session.scalar(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.job),
            selectinload(Application.negotiations),
            selectinload(Application.worker).selectinload(WorkerProfile.user),
            selectinload(Application.worker).selectinload(WorkerProfile.skills),
        )
    )
    if item is None:
        raise APIError(404, "Application not found")
    return item


def _consumer_owns_job(session: Session, user: User, job_id: UUID) -> bool:
    return session.scalar(
        select(ConsumerProfile.id).where(
            ConsumerProfile.user_id == user.id,
            ConsumerProfile.id == select(Job.consumer_id).where(Job.id == job_id).scalar_subquery(),
        )
    ) is not None


def _consumer_owns_application(session: Session, user: User, item: Application) -> bool:
    return _consumer_owns_job(session, user, item.job_id)


def _worker_owns_application(item: Application, user: User) -> bool:
    return item.worker.user_id == user.id


def _assert_application_open(item: Application) -> None:
    if item.status not in {ApplicationStatus.SUBMITTED, ApplicationStatus.COUNTER_OFFER}:
        raise APIError(409, "Application is no longer open for this action")


def _create_agreement(session: Session, item: Application, amount, user: User) -> AgreementResponse:
    locked_job = session.scalar(select(Job).where(Job.id == item.job_id).with_for_update())
    if locked_job is None:
        raise APIError(404, "Job not found")
    item.job = locked_job
    if item.job.scheduled_date is None or item.job.start_time is None or item.job.end_time is None:
        raise APIError(409, "A scheduled date, start time, and end time are required before hiring")
    validate_worker_schedule(
        session,
        item.worker_id,
        item.job.scheduled_date,
        item.job.start_time,
        item.job.end_time,
    )

    accepted_count = session.scalar(
        select(func.count(Agreement.id)).where(
            Agreement.job_id == item.job_id,
            Agreement.status.in_([AgreementStatus.PENDING, AgreementStatus.ACTIVE]),
        )
    ) or 0
    if accepted_count >= item.job.required_worker_count:
        raise APIError(409, "The job has reached its worker capacity")

    agreement = Agreement(
        job_id=item.job_id,
        worker_id=item.worker_id,
        agreed_price=amount,
        agreed_date=item.job.scheduled_date,
        start_time=item.job.start_time,
        end_time=item.job.end_time,
        worker_count=1,
        status=AgreementStatus.ACTIVE,
    )
    item.status = ApplicationStatus.ACCEPTED
    item.job.status = JobStatus.ACCEPTED
    session.add(agreement)
    session.commit()
    session.refresh(agreement)
    consumer_id = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == item.job.consumer_id))
    service = NotificationService()
    if consumer_id:
        service.create_notification(session, consumer_id, NotificationType.AGREEMENT_CREATED, "Agreement created", f"An agreement for {item.job.title} is now active.", "agreement", agreement.id, idempotency_key=f"agreement-created:{agreement.id}")
    service.create_notification(session, item.worker.user_id, NotificationType.AGREEMENT_CREATED, "Agreement created", f"An agreement for {item.job.title} is now active.", "agreement", agreement.id, idempotency_key=f"agreement-created:{agreement.id}")
    session.commit()
    return AgreementResponse(
        id=agreement.id,
        job_id=agreement.job_id,
        worker_id=agreement.worker_id,
        agreed_price=agreement.agreed_price,
        agreed_date=agreement.agreed_date,
        start_time=agreement.start_time,
        end_time=agreement.end_time,
        worker_count=agreement.worker_count,
        status=agreement.status.value,
    )


def apply_to_job(session: Session, user: User, job_id: UUID, data: ApplicationCreateRequest) -> ApplicationResponse:
    worker = session.scalar(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    job = session.scalar(select(Job).where(Job.id == job_id))
    if worker is None:
        raise APIError(409, "Worker profile is not available")
    if job is None:
        raise APIError(404, "Job not found")
    if job.status not in {JobStatus.POSTED, JobStatus.APPLICATIONS, JobStatus.ACCEPTED}:
        raise APIError(409, "Job is not accepting applications")
    if session.scalar(select(ConsumerProfile.id).where(ConsumerProfile.id == job.consumer_id, ConsumerProfile.user_id == user.id)):
        raise APIError(403, "A worker cannot apply to their own job")
    if session.scalar(select(Application.id).where(Application.job_id == job_id, Application.worker_id == worker.id)):
        raise APIError(409, "You have already applied to this job")

    item = Application(
        job_id=job_id,
        worker_id=worker.id,
        proposed_price=data.proposed_price,
        status=ApplicationStatus.SUBMITTED,
        submitted_at=datetime.now(timezone.utc),
    )
    job.status = JobStatus.APPLICATIONS
    session.add(item)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise APIError(409, "You have already applied to this job") from error
    created = _load_application(session, item.id)
    consumer_id = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == job.consumer_id))
    if consumer_id:
        NotificationService().create_notification(
            session, consumer_id, NotificationType.APPLICATION_SUBMITTED,
            "New job application", f"A worker applied to {job.title}.", "job", job.id,
            idempotency_key=f"application-submitted:{item.id}",
        )
        session.commit()
    return _application_response(created)


def list_my_applications(session: Session, user: User) -> list[ApplicationResponse]:
    worker = session.scalar(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    if worker is None:
        raise APIError(409, "Worker profile is not available")
    items = session.scalars(
        select(Application).where(Application.worker_id == worker.id).options(
            selectinload(Application.job), selectinload(Application.negotiations)
        ).order_by(Application.submitted_at.desc())
    ).all()
    return [_application_response(item) for item in items]


def list_applicants(session: Session, user: User, job_id: UUID) -> list[ApplicantResponse]:
    job = session.scalar(select(Job).where(Job.id == job_id))
    if job is None:
        raise APIError(404, "Job not found")
    if not _consumer_owns_job(session, user, job_id):
        raise APIError(403, "You may only view applicants for your own jobs")
    items = session.scalars(
        select(Application).where(Application.job_id == job_id).options(
            selectinload(Application.worker).selectinload(WorkerProfile.user),
            selectinload(Application.worker).selectinload(WorkerProfile.skills),
            selectinload(Application.negotiations),
        ).order_by(Application.submitted_at.asc())
    ).all()
    return [
        ApplicantResponse(
            id=item.id,
            worker_id=item.worker_id,
            worker_name=item.worker.user.name,
            worker_rating=item.worker.rating_average,
            worker_reliability=item.worker.reliability_score,
            worker_availability=item.worker.availability,
            proposed_price=item.proposed_price,
            status=item.status,
            submitted_at=item.submitted_at,
            skills=[skill.skill.name for skill in item.worker.skills],
            negotiations=[_negotiation_response(entry) for entry in item.negotiations],
        )
        for item in items
    ]


def accept_application(session: Session, user: User, application_id: UUID) -> AgreementResponse:
    item = _load_application(session, application_id)
    if not _consumer_owns_application(session, user, item):
        raise APIError(403, "Only the job owner may accept an application")
    _assert_application_open(item)
    latest_offer = session.scalar(
        select(Negotiation)
        .where(
            Negotiation.application_id == item.id,
            Negotiation.status == NegotiationStatus.PROPOSED,
        )
        .order_by(Negotiation.created_at.desc())
    )
    result = _create_agreement(session, item, latest_offer.proposed_amount if latest_offer else item.proposed_price, user)
    NotificationService().create_notification(session, item.worker.user_id, NotificationType.APPLICATION_ACCEPTED, "Application accepted", f"Your application for {item.job.title} was accepted.", "agreement", result.id, idempotency_key=f"application-accepted:{item.id}")
    session.commit()
    return result


def reject_application(session: Session, user: User, application_id: UUID) -> None:
    item = _load_application(session, application_id)
    if not _consumer_owns_application(session, user, item):
        raise APIError(403, "Only the job owner may reject an application")
    _assert_application_open(item)
    item.status = ApplicationStatus.REJECTED
    session.commit()
    NotificationService().create_notification(session, item.worker.user_id, NotificationType.APPLICATION_REJECTED, "Application rejected", f"Your application for {item.job.title} was rejected.", "job", item.job_id, idempotency_key=f"application-rejected:{item.id}")
    session.commit()


def withdraw_application(session: Session, user: User, application_id: UUID) -> None:
    item = _load_application(session, application_id)
    if not _worker_owns_application(item, user):
        raise APIError(403, "Only the applicant may withdraw this application")
    _assert_application_open(item)
    item.status = ApplicationStatus.WITHDRAWN
    item.withdrawn_at = datetime.now(timezone.utc)
    session.commit()
    consumer_id = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == item.job.consumer_id))
    if consumer_id:
        NotificationService().create_notification(session, consumer_id, NotificationType.APPLICATION_WITHDRAWN, "Application withdrawn", f"A worker withdrew an application for {item.job.title}.", "job", item.job_id, idempotency_key=f"application-withdrawn:{item.id}")
        session.commit()


def create_counter_offer(session: Session, user: User, application_id: UUID, data: CounterOfferRequest) -> NegotiationResponse:
    item = _load_application(session, application_id)
    if not (_worker_owns_application(item, user) or _consumer_owns_application(session, user, item)):
        raise APIError(403, "You are not a participant in this application")
    _assert_application_open(item)
    negotiation = Negotiation(
        job_id=item.job_id,
        application_id=item.id,
        initiated_by=user.id,
        proposed_amount=data.proposed_amount,
        status=NegotiationStatus.PROPOSED,
        message=data.message,
    )
    item.status = ApplicationStatus.COUNTER_OFFER
    session.add(negotiation)
    session.commit()
    session.refresh(negotiation)
    recipient = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == item.job.consumer_id)) if _worker_owns_application(item, user) else item.worker.user_id
    NotificationService().create_notification(session, recipient, NotificationType.COUNTER_OFFER_RECEIVED, "Counter-offer received", f"A counter-offer was submitted for {item.job.title}.", "application", item.id, idempotency_key=f"counter-offer-received:{negotiation.id}")
    session.commit()
    return _negotiation_response(negotiation)


def accept_negotiation(session: Session, user: User, negotiation_id: UUID) -> AgreementResponse:
    negotiation = session.scalar(
        select(Negotiation).where(Negotiation.id == negotiation_id).options(selectinload(Negotiation.application).selectinload(Application.job), selectinload(Negotiation.application).selectinload(Application.worker))
    )
    if negotiation is None or negotiation.application is None:
        raise APIError(404, "Negotiation not found")
    item = negotiation.application
    if negotiation.initiated_by == user.id:
        raise APIError(403, "The proposal initiator cannot accept their own negotiation")
    if not (_worker_owns_application(item, user) or _consumer_owns_application(session, user, item)):
        raise APIError(403, "You are not a participant in this negotiation")
    if negotiation.status is not NegotiationStatus.PROPOSED:
        raise APIError(409, "Negotiation is no longer open")
    negotiation.status = NegotiationStatus.ACCEPTED
    agreement = _create_agreement(session, item, negotiation.proposed_amount, user)
    consumer_id = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == item.job.consumer_id))
    service = NotificationService()
    for recipient in {consumer_id, item.worker.user_id} - {None}:
        service.create_notification(
            session, recipient, NotificationType.COUNTER_OFFER_ACCEPTED,
            "Counter-offer accepted", f"The counter-offer for {item.job.title} was accepted.",
            "application", item.id,
            idempotency_key=f"counter-offer-accepted:{negotiation.id}",
        )
    session.commit()
    return agreement


def reject_negotiation(session: Session, user: User, negotiation_id: UUID) -> None:
    negotiation = session.scalar(select(Negotiation).where(Negotiation.id == negotiation_id).options(selectinload(Negotiation.application)))
    if negotiation is None or negotiation.application is None:
        raise APIError(404, "Negotiation not found")
    item = _load_application(session, negotiation.application.id)
    if not (_worker_owns_application(item, user) or _consumer_owns_application(session, user, item)):
        raise APIError(403, "You are not a participant in this negotiation")
    if negotiation.status is not NegotiationStatus.PROPOSED:
        raise APIError(409, "Negotiation is no longer open")
    negotiation.status = NegotiationStatus.REJECTED
    item.status = ApplicationStatus.REJECTED
    session.commit()
    consumer_id = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == item.job.consumer_id))
    service = NotificationService()
    for recipient in {consumer_id, item.worker.user_id} - {None}:
        service.create_notification(
            session, recipient, NotificationType.COUNTER_OFFER_REJECTED,
            "Counter-offer rejected", f"The counter-offer for {item.job.title} was rejected.",
            "application", item.id,
            idempotency_key=f"counter-offer-rejected:{negotiation.id}",
        )
    session.commit()