from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.db.models.enums import ComplaintCategory, ComplaintStatus, DisputeStatus, UserRole
from app.db.models.users import User
from app.db.session import get_db
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
from app.services.issue_service import (
    admin_complaints,
    admin_disputes,
    create_complaint,
    create_dispute,
    dispute_detail,
    get_complaint,
    my_complaints,
    respond_to_complaint,
    resolve_dispute,
    update_complaint_status,
    update_dispute_status,
)


router = APIRouter(tags=["complaints", "disputes"])


@router.post("/complaints", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
def create_complaint_route(data: ComplaintCreateRequest, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> ComplaintResponse:
    return create_complaint(session, user, data)


@router.get("/complaints/my", response_model=ComplaintListResponse)
def get_my_complaints(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> ComplaintListResponse:
    return my_complaints(session, user, page, page_size)


@router.get("/complaints/{complaint_id}", response_model=ComplaintResponse)
def get_complaint_route(complaint_id: UUID, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> ComplaintResponse:
    return get_complaint(session, user, complaint_id)


@router.get("/admin/complaints", response_model=ComplaintListResponse)
def list_admin_complaints(
    status_filter: ComplaintStatus | None = Query(None, alias="status"),
    category: ComplaintCategory | None = None,
    reporter_role: UserRole | None = None,
    job_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin), session: Session = Depends(get_db),
) -> ComplaintListResponse:
    return admin_complaints(session, status_filter, category, reporter_role, job_id, page, page_size)


@router.get("/admin/complaints/{complaint_id}", response_model=ComplaintResponse)
def admin_complaint_detail(complaint_id: UUID, _: User = Depends(require_admin), session: Session = Depends(get_db)) -> ComplaintResponse:
    return get_complaint(session, _, complaint_id)


@router.patch("/admin/complaints/{complaint_id}/status", response_model=ComplaintResponse)
def admin_complaint_status(complaint_id: UUID, data: ComplaintStatusRequest, _: User = Depends(require_admin), session: Session = Depends(get_db)) -> ComplaintResponse:
    return update_complaint_status(session, complaint_id, data)


@router.post("/admin/complaints/{complaint_id}/response", response_model=ComplaintResponse)
def admin_complaint_response(complaint_id: UUID, data: AdminResponseRequest, _: User = Depends(require_admin), session: Session = Depends(get_db)) -> ComplaintResponse:
    return respond_to_complaint(session, complaint_id, data)


@router.post("/jobs/{job_id}/disputes", response_model=DisputeResponse, status_code=status.HTTP_201_CREATED)
def create_job_dispute(job_id: UUID, data: DisputeCreateRequest, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> DisputeResponse:
    return create_dispute(session, user, job_id, data)


@router.get("/admin/disputes", response_model=list[DisputeResponse])
def list_admin_disputes(status_filter: DisputeStatus | None = Query(None, alias="status"), job_id: UUID | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), _: User = Depends(require_admin), session: Session = Depends(get_db)) -> list[DisputeResponse]:
    return admin_disputes(session, status_filter, job_id, page, page_size)


@router.get("/admin/disputes/{dispute_id}", response_model=DisputeContextResponse)
def get_admin_dispute(dispute_id: UUID, _: User = Depends(require_admin), session: Session = Depends(get_db)) -> DisputeContextResponse:
    return dispute_detail(session, _, dispute_id)


@router.get("/disputes/{dispute_id}", response_model=DisputeContextResponse)
def get_associated_dispute(dispute_id: UUID, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> DisputeContextResponse:
    return dispute_detail(session, user, dispute_id)


@router.patch("/admin/disputes/{dispute_id}/status", response_model=DisputeResponse)
def admin_dispute_status(dispute_id: UUID, data: DisputeStatusRequest, _: User = Depends(require_admin), session: Session = Depends(get_db)) -> DisputeResponse:
    return update_dispute_status(session, dispute_id, data)


@router.post("/admin/disputes/{dispute_id}/resolve", response_model=DisputeResponse)
def admin_resolve_dispute(dispute_id: UUID, data: DisputeResolutionRequest, _: User = Depends(require_admin), session: Session = Depends(get_db)) -> DisputeResponse:
    return resolve_dispute(session, dispute_id, data)