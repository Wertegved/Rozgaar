from datetime import date, time
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Index, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import AvailabilityStatus


class WorkerAvailability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "worker_availability"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_worker_availability_time_order"),
        Index("ix_worker_availability_worker_date", "worker_id", "available_date"),
    )

    worker_id: Mapped[UUID] = mapped_column(
        ForeignKey("worker_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    available_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[AvailabilityStatus] = mapped_column(
        Enum(AvailabilityStatus, name="availability_status"),
        default=AvailabilityStatus.AVAILABLE,
        nullable=False,
    )
    worker: Mapped["WorkerProfile"] = relationship()