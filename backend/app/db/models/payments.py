from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import PaymentStatus, PaymentType


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("agreed_amount >= 0", name="ck_payments_agreed_non_negative"),
        CheckConstraint("advance_amount >= 0", name="ck_payments_advance_non_negative"),
        CheckConstraint("final_amount >= 0", name="ck_payments_final_non_negative"),
        Index("ix_payments_job_id", "job_id"),
    )

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    agreement_id: Mapped[UUID | None] = mapped_column(ForeignKey("agreements.id", ondelete="RESTRICT"))
    payer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    payee_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    agreed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    advance_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    final_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    payment_type: Mapped[PaymentType] = mapped_column(Enum(PaymentType, name="payment_type"), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus, name="payment_status"), nullable=False)
    transaction_reference: Mapped[str | None] = mapped_column(String(255), unique=True)
    job: Mapped["Job"] = relationship(back_populates="payments")
    agreement: Mapped["Agreement | None"] = relationship(back_populates="payments")