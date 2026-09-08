from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.models.enums import ApplicationStatus


class Application(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint("proposed_price >= 0", name="ck_applications_price_non_negative"),
        UniqueConstraint("job_id", "worker_id", name="uq_applications_job_worker"),
        Index("ix_applications_job_id", "job_id"),
        Index("ix_applications_worker_id", "worker_id"),
    )

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    worker_id: Mapped[UUID] = mapped_column(ForeignKey("worker_profiles.id", ondelete="RESTRICT"))
    proposed_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"), default=ApplicationStatus.SUBMITTED, nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    job: Mapped["Job"] = relationship(back_populates="applications")
    worker: Mapped["WorkerProfile"] = relationship()
    negotiations: Mapped[list["Negotiation"]] = relationship(back_populates="application")