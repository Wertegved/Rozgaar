from datetime import date, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import AgreementStatus


class Agreement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agreements"
    __table_args__ = (
        CheckConstraint("agreed_price >= 0", name="ck_agreements_price_non_negative"),
        CheckConstraint("worker_count > 0", name="ck_agreements_worker_count_positive"),
        Index("ix_agreements_job_id", "job_id"),
        Index("ix_agreements_worker_id", "worker_id"),
    )

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    worker_id: Mapped[UUID] = mapped_column(ForeignKey("worker_profiles.id", ondelete="RESTRICT"))
    agreed_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    agreed_date: Mapped[date] = mapped_column(nullable=False)
    start_time: Mapped[time] = mapped_column(nullable=False)
    end_time: Mapped[time] = mapped_column(nullable=False)
    worker_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[AgreementStatus] = mapped_column(
        Enum(AgreementStatus, name="agreement_status"), default=AgreementStatus.PENDING, nullable=False
    )
    job: Mapped["Job"] = relationship(back_populates="agreements")
    worker: Mapped["WorkerProfile"] = relationship()
    payments: Mapped[list["Payment"]] = relationship(back_populates="agreement")
    cancellations: Mapped[list["Cancellation"]] = relationship(back_populates="agreement")