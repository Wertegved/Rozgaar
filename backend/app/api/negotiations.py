from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.db.models.negotiations import Negotiation
from app.db.models.users import User
from app.core.errors import APIError
from app.schemas.applications import AgreementResponse, CounterOfferRequest, NegotiationResponse
from app.services.application_service import accept_negotiation, create_counter_offer, reject_negotiation


router = APIRouter(prefix="/negotiations", tags=["negotiations"])


@router.post("/{negotiation_id}/accept", response_model=AgreementResponse)
def accept(
    negotiation_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> AgreementResponse:
    return accept_negotiation(session, user, negotiation_id)


@router.post("/{negotiation_id}/counter-offer", response_model=NegotiationResponse)
def counter_offer(
    negotiation_id: UUID,
    data: CounterOfferRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> NegotiationResponse:
    negotiation = session.scalar(select(Negotiation).where(Negotiation.id == negotiation_id))
    if negotiation is None or negotiation.application_id is None:
        raise APIError(404, "Negotiation not found")
    return create_counter_offer(session, user, negotiation.application_id, data)


@router.post("/{negotiation_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject(
    negotiation_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    reject_negotiation(session, user, negotiation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)