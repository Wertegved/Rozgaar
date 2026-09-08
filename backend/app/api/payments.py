from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin, require_consumer, require_worker
from app.db.models.users import User
from app.db.session import get_db
from app.schemas.payments import PaymentListResponse, PaymentResponse, SimulatedCardRequest
from app.services.payment_service import agreement_payments, get_payment, pay_advance, user_payments


router = APIRouter(tags=["payments"])


@router.post("/agreements/{agreement_id}/payments/advance", response_model=PaymentResponse)
def pay_agreement_advance(
    agreement_id: UUID,
    data: SimulatedCardRequest | None = None,
    user: User = Depends(require_consumer),
    session: Session = Depends(get_db),
) -> PaymentResponse:
    return pay_advance(session, user, agreement_id, payment_details=data)


@router.get("/agreements/{agreement_id}/payments", response_model=PaymentListResponse)
def get_agreement_payments(
    agreement_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PaymentListResponse:
    return agreement_payments(session, user, agreement_id)


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment_detail(
    payment_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> PaymentResponse:
    return get_payment(session, user, payment_id)


@router.get("/workers/me/payments", response_model=PaymentListResponse)
def get_worker_payments(
    user: User = Depends(require_worker),
    session: Session = Depends(get_db),
) -> PaymentListResponse:
    return user_payments(session, user)


@router.get("/consumers/me/payments", response_model=PaymentListResponse)
def get_consumer_payments(
    user: User = Depends(require_consumer),
    session: Session = Depends(get_db),
) -> PaymentListResponse:
    return user_payments(session, user)


@router.get("/admin/payments", response_model=PaymentListResponse)
def get_admin_payments(
    user: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> PaymentListResponse:
    return user_payments(session, user)