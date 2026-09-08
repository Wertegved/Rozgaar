from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models.users import User
from app.db.models.enums import UserRole
from app.db.session import get_db
from app.providers.base import PaymentProvider
from app.schemas.completion import CompletionEvidenceUploadResponse, CompletionResponse, CompletionSubmitRequest
from app.services.completion_service import get_completion, submit_completion, upload_completion_evidence


router = APIRouter(prefix="/jobs", tags=["completion"])


@router.post("/{job_id}/completion/worker", response_model=CompletionResponse)
def worker_completion(job_id: UUID, data: CompletionSubmitRequest, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> CompletionResponse:
    return submit_completion(session, user, job_id, data, UserRole.WORKER)


@router.post("/{job_id}/completion/worker/evidence", response_model=CompletionEvidenceUploadResponse)
def worker_evidence_upload(job_id: UUID, file: UploadFile = File(...), user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> CompletionEvidenceUploadResponse:
    return upload_completion_evidence(session, user, job_id, UserRole.WORKER, file)


@router.post("/{job_id}/completion/consumer", response_model=CompletionResponse)
def consumer_completion(job_id: UUID, data: CompletionSubmitRequest, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> CompletionResponse:
    return submit_completion(session, user, job_id, data, UserRole.CONSUMER)


@router.post("/{job_id}/completion/consumer/evidence", response_model=CompletionEvidenceUploadResponse)
def consumer_evidence_upload(job_id: UUID, file: UploadFile = File(...), user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> CompletionEvidenceUploadResponse:
    return upload_completion_evidence(session, user, job_id, UserRole.CONSUMER, file)


@router.get("/{job_id}/completion", response_model=CompletionResponse)
def completion_status(job_id: UUID, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> CompletionResponse:
    return get_completion(session, user, job_id)