from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import ComplaintCategory, ComplaintStatus


class Complaint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "complaints"
    __table_args__ = (Index("ix_complaints_status", "status"),)

    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    raised_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    category: Mapped[ComplaintCategory] = mapped_column(Enum(ComplaintCategory, name="complaint_category"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus, name="complaint_status"), default=ComplaintStatus.NEW, nullable=False
    )
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    job: Mapped["Job | None"] = relationship(back_populates="complaints")