from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.db.models.agreements import Agreement
from app.db.models.completion import Completion, CompletionEvidence, CompletionWorkerState
from app.db.models.enums import AgreementStatus, ApplicationStatus, EvidenceType, JobStatus, PaymentStatus, PaymentType, UserRole
from app.db.models.jobs import Job
from app.db.models.payments import Payment
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.providers.base import PaymentProvider
from app.services.payment_service import release_final_payment
from app.schemas.completion import CompletionEvidenceUploadResponse, CompletionResponse, CompletionSubmitRequest
from app.core.config import get_settings
from fastapi import UploadFile
from app.db.models.enums import NotificationType
from app.services.notification_service import NotificationService


MAX_COMPLETION_IMAGE_BYTES = 15 * 1024 * 1024
COMPLETION_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}


def upload_completion_evidence(session: Session, user: User, job_id: UUID, expected_role: UserRole, file: UploadFile) -> CompletionEvidenceUploadResponse:
    if file.content_type not in COMPLETION_IMAGE_TYPES:
        raise APIError(422, "Completion evidence must be a JPG, JPEG, or PNG image")
    filename = PurePosixPath(file.filename or "completion-photo").name
    extension = ".jpg" if filename.lower().endswith((".jpg", ".jpeg")) else ".png" if filename.lower().endswith(".png") else ""
    if not extension:
        raise APIError(422, "Completion evidence must use a .jpg, .jpeg, or .png filename")
    content = file.file.read(MAX_COMPLETION_IMAGE_BYTES + 1)
    if len(content) > MAX_COMPLETION_IMAGE_BYTES:
        raise APIError(413, "Completion evidence must be 15 MB or smaller")
    valid_signature = content.startswith(b"\xff\xd8\xff") if extension == ".jpg" else content.startswith(b"\x89PNG\r\n\x1a\n")
    if not valid_signature:
        raise APIError(422, "The selected file is not a valid JPG, JPEG, or PNG image")
    agreement = _job_agreement(session, job_id)
    _authorized(session, user, agreement, expected_role)
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise APIError(503, "Private completion storage is not configured")
    storage_path = f"{job_id}/{expected_role.value.lower()}/{uuid4()}{extension}"
    request = Request(
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/completion-evidence/{storage_path}",
        data=content,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
            "Content-Type": file.content_type,
            "x-upsert": "false",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status not in {200, 201}: raise APIError(502, "Private completion storage rejected the upload")
    except (HTTPError, URLError, TimeoutError) as error:
        raise APIError(502, "Private completion storage upload failed") from error
    return CompletionEvidenceUploadResponse(storage_bucket="completion-evidence", storage_path=storage_path, filename=filename, size_bytes=len(content))


def _job_agreement(session: Session, job_id: UUID) -> Agreement:
    agreement = session.scalar(
        select(Agreement).where(
            Agreement.job_id == job_id,
            Agreement.status == AgreementStatus.ACTIVE,
        ).order_by(Agreement.created_at)
    )
    if agreement is None:
        raise APIError(409, "No active agreement exists for this job")
    return agreement


def _completion(session: Session, job_id: UUID) -> Completion:
    item = session.scalar(select(Completion).where(Completion.job_id == job_id).with_for_update())
    if item is None:
        item = Completion(job_id=job_id)
        session.add(item)
        session.flush()
    return item


def _authorized(session: Session, user: User, agreement: Agreement, role: UserRole) -> WorkerProfile | None:
    if user.role is not role:
        raise APIError(403, "This completion action is not allowed for your role")
    if role is UserRole.WORKER:
        worker = session.scalar(select(WorkerProfile).where(WorkerProfile.id == agreement.worker_id, WorkerProfile.user_id == user.id))
        if worker is None:
            raise APIError(403, "Worker is not assigned to this agreement")
        return worker
    owner = session.scalar(select(ConsumerProfile.id).where(ConsumerProfile.id == agreement.job.consumer_id, ConsumerProfile.user_id == user.id))
    if owner is None:
        raise APIError(403, "Consumer does not own this job")
    return None


def _state(session: Session, agreement: Agreement) -> CompletionWorkerState:
    state = session.scalar(select(CompletionWorkerState).where(CompletionWorkerState.agreement_id == agreement.id).with_for_update())
    if state is None:
        state = CompletionWorkerState(job_id=agreement.job_id, agreement_id=agreement.id, worker_id=agreement.worker_id)
        session.add(state)
        session.flush()
    return state


def _evaluate(session: Session, job: Job, completion: Completion, provider: PaymentProvider | None) -> None:
    active_agreements = session.scalars(select(Agreement).where(Agreement.job_id == job.id, Agreement.status == AgreementStatus.ACTIVE)).all()
    states = [session.scalar(select(CompletionWorkerState).where(CompletionWorkerState.agreement_id == agreement.id)) for agreement in active_agreements]
    all_workers_confirmed = bool(states) and all(state is not None and state.worker_confirmed_at is not None for state in states)
    worker_evidence_count = session.scalar(select(func.count(CompletionEvidence.id)).where(CompletionEvidence.job_id == job.id, CompletionEvidence.evidence_type == EvidenceType.WORKER_COMPLETION)) or 0
    consumer_evidence = session.scalar(select(CompletionEvidence.id).where(CompletionEvidence.job_id == job.id, CompletionEvidence.evidence_type == EvidenceType.CONSUMER_COMPLETION)) is not None
    if not (all_workers_confirmed and worker_evidence_count >= len(active_agreements) and completion.consumer_confirmed_at and consumer_evidence):
        return
    agreement = active_agreements[0]
    payment = release_final_payment(session, agreement.id, provider, commit=False, payment_details=getattr(completion, "payment_details", None))
    if payment.status is PaymentStatus.COMPLETED:
        job.status = JobStatus.COMPLETED


def submit_completion(session: Session, user: User, job_id: UUID, data: CompletionSubmitRequest, expected_role: UserRole, provider: PaymentProvider | None = None) -> CompletionResponse:
    if data.storage_bucket != "completion-evidence":
        raise APIError(422, "Completion evidence must use the private completion-evidence bucket")
    job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if job is None:
        raise APIError(404, "Job not found")
    if job.status is JobStatus.COMPLETED:
        raise APIError(409, "Job is already completed")
    agreement = _job_agreement(session, job_id)
    _authorized(session, user, agreement, expected_role)
    completion = _completion(session, job_id)
    now = datetime.now(timezone.utc)
    if expected_role is UserRole.WORKER:
        state = _state(session, agreement)
        if state.worker_confirmed_at is not None:
            raise APIError(409, "Worker completion was already submitted")
        state.worker_confirmed_at = now
        evidence_type = EvidenceType.WORKER_COMPLETION
    else:
        if completion.consumer_confirmed_at is not None:
            raise APIError(409, "Consumer completion was already submitted")
        completion.consumer_confirmed_at = now
        evidence_type = EvidenceType.CONSUMER_COMPLETION
    evidence = CompletionEvidence(
        job_id=job_id, agreement_id=agreement.id, completion_id=completion.id,
        uploaded_by=user.id, uploader_role=user.role.value, evidence_type=evidence_type,
        storage_bucket=data.storage_bucket, storage_path=data.storage_path,
    )
    session.add(evidence)
    session.flush()
    _evaluate(session, job, completion, provider)
    session.commit()
    if expected_role is UserRole.WORKER:
        recipient = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == job.consumer_id))
    else:
        recipient = session.scalar(select(WorkerProfile.user_id).where(WorkerProfile.id == agreement.worker_id))
    if recipient:
        NotificationService().create_notification(
            session, recipient, NotificationType.COMPLETION_CONFIRMED,
            "Completion confirmation received", f"A participant submitted completion confirmation for {job.title}.",
            "job", job.id,
            idempotency_key=f"completion-confirmed:{evidence.id}",
        )
        session.commit()
    if job.status is JobStatus.COMPLETED:
        consumer_id = session.scalar(select(ConsumerProfile.user_id).where(ConsumerProfile.id == job.consumer_id))
        worker_ids = session.scalars(
            select(WorkerProfile.user_id).join(Agreement, Agreement.worker_id == WorkerProfile.id).where(Agreement.job_id == job.id)
        ).all()
        service = NotificationService()
        for recipient in {consumer_id, *worker_ids} - {None}:
            service.create_notification(
                session, recipient, NotificationType.JOB_COMPLETED,
                "Job completed", f"The job {job.title} has been completed.",
                "job", job.id, idempotency_key=f"job-completed:{job.id}",
            )
        session.commit()
    return get_completion(session, user, job_id)


def get_completion(session: Session, user: User, job_id: UUID) -> CompletionResponse:
    agreement = _job_agreement(session, job_id)
    if user.role is UserRole.WORKER:
        _authorized(session, user, agreement, UserRole.WORKER)
    elif user.role is UserRole.CONSUMER:
        _authorized(session, user, agreement, UserRole.CONSUMER)
    elif user.role is not UserRole.ADMIN:
        raise APIError(403, "Completion access denied")
    completion = session.scalar(select(Completion).where(Completion.job_id == job_id))
    states = session.scalars(select(CompletionWorkerState).where(CompletionWorkerState.job_id == job_id)).all()
    evidence = session.scalars(select(CompletionEvidence).where(CompletionEvidence.job_id == job_id)).all()
    final = session.scalar(select(Payment).where(Payment.job_id == job_id, Payment.payment_type == PaymentType.FINAL, Payment.status == PaymentStatus.COMPLETED))
    return CompletionResponse(
        job_id=job_id,
        worker_evidence=any(item.evidence_type is EvidenceType.WORKER_COMPLETION for item in evidence),
        worker_confirmed=bool(states) and all(item.worker_confirmed_at is not None for item in states),
        consumer_evidence=any(item.evidence_type is EvidenceType.CONSUMER_COMPLETION for item in evidence),
        consumer_confirmed=completion is not None and completion.consumer_confirmed_at is not None,
        final_payment_completed=final is not None,
        job_completed=job_id == (completion.job_id if completion else None) and final is not None,
        evidence_ids=[item.id for item in evidence],
        updated_at=completion.updated_at if completion else None,
    )