from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.errors import APIError
from app.db.models.agreements import Agreement
from app.db.models.enums import AgreementStatus, PaymentStatus, PaymentType, UserRole
from app.db.models.payments import Payment
from app.db.models.jobs import Job
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.providers.base import PaymentProvider
from app.providers.simulated import SimulatedPaymentProvider
from app.schemas.payments import PaymentListResponse, PaymentResponse
from app.db.models.enums import NotificationType
from app.services.notification_service import NotificationService


CENT = Decimal("0.01")


def _payment_response(payment: Payment) -> PaymentResponse:
    return PaymentResponse.model_validate(payment)


def _agreement_with_context(session: Session, agreement_id: UUID, lock: bool = False) -> Agreement:
    statement = (
        select(Agreement)
        .where(Agreement.id == agreement_id)
        .options(selectinload(Agreement.job))
    )
    if lock:
        statement = statement.with_for_update()
    agreement = session.scalar(statement)
    if agreement is None:
        raise APIError(404, "Agreement not found")
    return agreement


def _agreement_parties(session: Session, agreement: Agreement) -> tuple[UUID, UUID]:
    consumer_user_id = session.scalar(
        select(ConsumerProfile.user_id).where(ConsumerProfile.id == agreement.job.consumer_id)
    )
    worker_user_id = session.scalar(
        select(WorkerProfile.user_id).where(WorkerProfile.id == agreement.worker_id)
    )
    if consumer_user_id is None or worker_user_id is None:
        raise APIError(409, "Agreement parties are not available")
    return consumer_user_id, worker_user_id


def _amounts(agreement: Agreement) -> tuple[Decimal, Decimal]:
    agreed = Decimal(agreement.agreed_price).quantize(CENT)
    percentage = Decimal(get_settings().payment_advance_percentage) / Decimal("100")
    advance = (agreed * percentage).quantize(CENT, rounding=ROUND_HALF_UP)
    final = (agreed - advance).quantize(CENT)
    if advance < 0 or final < 0 or advance + final != agreed:
        raise APIError(409, "Payment amounts are inconsistent with the agreement")
    return advance, final


def pay_advance(
    session: Session,
    user: User,
    agreement_id: UUID,
    provider: PaymentProvider | None = None,
) -> PaymentResponse:
    agreement = _agreement_with_context(session, agreement_id, lock=True)
    if agreement.status is not AgreementStatus.ACTIVE:
        raise APIError(409, "Advance payment requires an active locked agreement")
    payer_id, payee_id = _agreement_parties(session, agreement)
    if user.role is not UserRole.CONSUMER or user.id != payer_id:
        raise APIError(403, "Only the agreement consumer may pay the advance")
    advance, final = _amounts(agreement)
    existing = session.scalar(
        select(Payment).where(
            Payment.agreement_id == agreement.id,
            Payment.payment_type == PaymentType.ADVANCE,
        )
    )
    if existing is not None and existing.status is PaymentStatus.COMPLETED:
        return _payment_response(existing)

    if provider is None:
        if get_settings().payment_provider != "simulated":
            raise APIError(500, "Only the simulated payment provider is configured")
        provider = SimulatedPaymentProvider()
    result = provider.create_payment(advance, {"agreement_id": str(agreement.id), "payment_type": "ADVANCE"})
    if existing is None:
        existing = Payment(
            job_id=agreement.job_id,
            agreement_id=agreement.id,
            payer_id=payer_id,
            payee_id=payee_id,
            agreed_amount=agreement.agreed_price,
            advance_amount=advance,
            final_amount=final,
            payment_type=PaymentType.ADVANCE,
            status=PaymentStatus.COMPLETED if result.success else PaymentStatus.FAILED,
            transaction_reference=result.reference,
        )
        session.add(existing)
    else:
        existing.status = PaymentStatus.COMPLETED if result.success else PaymentStatus.FAILED
        existing.transaction_reference = result.reference
    if result.success:
        final_payment = session.scalar(
            select(Payment).where(
                Payment.agreement_id == agreement.id,
                Payment.payment_type == PaymentType.FINAL,
            )
        )
        if final_payment is None:
            session.add(
                Payment(
                    job_id=agreement.job_id,
                    agreement_id=agreement.id,
                    payer_id=payer_id,
                    payee_id=payee_id,
                    agreed_amount=agreement.agreed_price,
                    advance_amount=advance,
                    final_amount=final,
                    payment_type=PaymentType.FINAL,
                    status=PaymentStatus.PENDING,
                )
            )
    session.commit()
    session.refresh(existing)
    if not result.success:
        service = NotificationService()
        for recipient in {payer_id, payee_id}:
            service.create_notification(
                session, recipient, NotificationType.PAYMENT_FAILED,
                "Payment failed", "The advance payment could not be completed.",
                "agreement", agreement.id, idempotency_key=f"advance-payment-failed:{agreement.id}",
            )
        session.commit()
        raise APIError(409, "Simulated advance payment failed")
    service = NotificationService()
    for recipient in {payer_id, payee_id}:
        service.create_notification(
            session, recipient, NotificationType.ADVANCE_PAYMENT_COMPLETED,
            "Advance payment completed", "An advance payment for your agreement was completed.",
            "agreement", agreement.id,
            idempotency_key=f"advance-payment-completed:{agreement.id}",
        )
    session.commit()
    return _payment_response(existing)


def agreement_payments(session: Session, user: User, agreement_id: UUID) -> PaymentListResponse:
    agreement = _agreement_with_context(session, agreement_id)
    payer_id, payee_id = _agreement_parties(session, agreement)
    if user.role is not UserRole.ADMIN and user.id not in {payer_id, payee_id}:
        raise APIError(403, "You may not view these payments")
    payments = session.scalars(
        select(Payment).where(Payment.agreement_id == agreement_id).order_by(Payment.created_at)
    ).all()
    return PaymentListResponse(
        items=[_payment_response(item) for item in payments],
        simulated_transaction_value=sum(
            (
                item.advance_amount if item.payment_type is PaymentType.ADVANCE else item.final_amount
                for item in payments
                if item.status is PaymentStatus.COMPLETED
            ),
            Decimal("0.00"),
        ),
    )


def user_payments(session: Session, user: User) -> PaymentListResponse:
    if user.role is UserRole.CONSUMER:
        predicate = Payment.payer_id == user.id
    elif user.role is UserRole.WORKER:
        predicate = Payment.payee_id == user.id
    else:
        predicate = Payment.id.is_not(None)
    payments = session.scalars(select(Payment).where(predicate).order_by(Payment.created_at.desc())).all()
    return PaymentListResponse(
        items=[_payment_response(item) for item in payments],
        simulated_transaction_value=sum(
            (
                item.advance_amount if item.payment_type is PaymentType.ADVANCE else item.final_amount
                for item in payments
                if item.status is PaymentStatus.COMPLETED
            ),
            Decimal("0.00"),
        ),
    )


def get_payment(session: Session, user: User, payment_id: UUID) -> PaymentResponse:
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise APIError(404, "Payment not found")
    if user.role is not UserRole.ADMIN and user.id not in {payment.payer_id, payment.payee_id}:
        raise APIError(403, "You may not view this payment")
    return _payment_response(payment)


def release_final_payment(
    session: Session,
    agreement_id: UUID,
    provider: PaymentProvider | None = None,
    commit: bool = True,
) -> PaymentResponse:
    agreement = _agreement_with_context(session, agreement_id, lock=True)
    if agreement.status is not AgreementStatus.ACTIVE:
        raise APIError(409, "Final payment requires an active agreement")
    payer_id, payee_id = _agreement_parties(session, agreement)
    advance = session.scalar(
        select(Payment).where(
            Payment.agreement_id == agreement_id,
            Payment.payment_type == PaymentType.ADVANCE,
            Payment.status == PaymentStatus.COMPLETED,
        )
    )
    if advance is None:
        raise APIError(409, "A completed advance payment is required")
    _, final_amount = _amounts(agreement)
    existing = session.scalar(
        select(Payment).where(Payment.agreement_id == agreement_id, Payment.payment_type == PaymentType.FINAL)
    )
    if existing is not None and existing.status is PaymentStatus.COMPLETED:
        return _payment_response(existing)
    if provider is None:
        if get_settings().payment_provider != "simulated":
            raise APIError(500, "Only the simulated payment provider is configured")
        provider = SimulatedPaymentProvider()
    result = provider.create_payment(final_amount, {"agreement_id": str(agreement_id), "payment_type": "FINAL"})
    if existing is None:
        existing = Payment(
            job_id=agreement.job_id,
            agreement_id=agreement_id,
            payer_id=payer_id,
            payee_id=payee_id,
            agreed_amount=agreement.agreed_price,
            advance_amount=advance.advance_amount,
            final_amount=final_amount,
            payment_type=PaymentType.FINAL,
            status=PaymentStatus.COMPLETED if result.success else PaymentStatus.FAILED,
            transaction_reference=result.reference,
        )
        session.add(existing)
    else:
        existing.status = PaymentStatus.COMPLETED if result.success else PaymentStatus.FAILED
        existing.transaction_reference = result.reference
    session.flush()
    if result.success and commit:
        session.commit()
    elif not result.success:
        session.commit()
    session.refresh(existing)
    if not result.success:
        service = NotificationService()
        for recipient in (payer_id, payee_id):
            service.create_notification(
                session, recipient, NotificationType.PAYMENT_FAILED,
                "Payment failed", "The final payment could not be completed.",
                "agreement", agreement.id, idempotency_key=f"final-payment-failed:{agreement.id}",
            )
        session.commit()
        raise APIError(409, "Simulated final payment failed")
    service = NotificationService()
    for recipient in (payer_id, payee_id):
        service.create_notification(
            session, recipient, NotificationType.FINAL_PAYMENT_COMPLETED,
            "Final payment completed", "Final payment for your completed job was processed.",
            "agreement", agreement.id,
            idempotency_key=f"final-payment-completed:{agreement.id}",
        )
    session.commit()
    return _payment_response(existing)