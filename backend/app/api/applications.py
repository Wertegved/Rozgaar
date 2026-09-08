from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_consumer, require_worker
from app.db.models.users import User
from app.db.session import get_db
from app.schemas.applications import (
    AgreementResponse,
    ApplicantResponse,
    ApplicationCreateRequest,
    ApplicationResponse,
    CounterOfferRequest,
    NegotiationResponse,
)
from app.services.application_service import (
    accept_application,
    create_counter_offer,
    list_applicants,
    list_my_applications,
    reject_application,
    withdraw_application,
    apply_to_job,
)


router = APIRouter(tags=["applications"])


@router.post("/jobs/{job_id}/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def apply(
    job_id: UUID,
    data: ApplicationCreateRequest,
    user: User = Depends(require_worker),
    session: Session = Depends(get_db),
) -> ApplicationResponse:
    return apply_to_job(session, user, job_id, data)


@router.get("/applications/my", response_model=list[ApplicationResponse])
def my_applications(
    user: User = Depends(require_worker), session: Session = Depends(get_db)
) -> list[ApplicationResponse]:
    return list_my_applications(session, user)


@router.get("/jobs/{job_id}/applications", response_model=list[ApplicantResponse])
def applicants(
    job_id: UUID,
    user: User = Depends(require_consumer),
    session: Session = Depends(get_db),
) -> list[ApplicantResponse]:
    return list_applicants(session, user, job_id)


@router.post("/applications/{application_id}/accept", response_model=AgreementResponse)
def accept(
    application_id: UUID,
    user: User = Depends(require_consumer),
    session: Session = Depends(get_db),
) -> AgreementResponse:
    return accept_application(session, user, application_id)


@router.post("/applications/{application_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject(
    application_id: UUID,
    user: User = Depends(require_consumer),
    session: Session = Depends(get_db),
) -> Response:
    reject_application(session, user, application_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/applications/{application_id}/withdraw", status_code=status.HTTP_204_NO_CONTENT)
def withdraw(
    application_id: UUID,
    user: User = Depends(require_worker),
    session: Session = Depends(get_db),
) -> Response:
    withdraw_application(session, user, application_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/applications/{application_id}/counter-offer", response_model=NegotiationResponse)
def counter_offer(
    application_id: UUID,
    data: CounterOfferRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> NegotiationResponse:
    return create_counter_offer(session, user, application_id, data)