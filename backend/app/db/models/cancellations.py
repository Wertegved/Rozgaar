from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import CancellationStatus


class Cancellation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cancellations"
    __table_args__ = (Index("ix_cancellations_job_id", "job_id"),)

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    agreement_id: Mapped[UUID | None] = mapped_column(ForeignKey("agreements.id", ondelete="RESTRICT"))
    cancelled_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[CancellationStatus] = mapped_column(
        Enum(CancellationStatus, name="cancellation_status"), default=CancellationStatus.REQUESTED, nullable=False
    )
    job: Mapped["Job"] = relationship(back_populates="cancellations")
    agreement: Mapped["Agreement | None"] = relationship(back_populates="cancellations")