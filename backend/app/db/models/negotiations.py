from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import NegotiationStatus


class Negotiation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "negotiations"
    __table_args__ = (
        CheckConstraint("proposed_amount >= 0", name="ck_negotiations_amount_non_negative"),
        Index("ix_negotiations_job_id", "job_id"),
    )

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    application_id: Mapped[UUID | None] = mapped_column(ForeignKey("applications.id", ondelete="RESTRICT"))
    initiated_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    proposed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[NegotiationStatus] = mapped_column(
        Enum(NegotiationStatus, name="negotiation_status"), nullable=False
    )
    message: Mapped[str | None] = mapped_column(String(1000))
    job: Mapped["Job"] = relationship(back_populates="negotiations")
    application: Mapped["Application | None"] = relationship(back_populates="negotiations")