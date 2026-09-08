from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import DisputeStatus


class Dispute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "disputes"
    __table_args__ = (Index("ix_disputes_status", "status"),)

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    raised_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DisputeStatus] = mapped_column(
        Enum(DisputeStatus, name="dispute_status"), default=DisputeStatus.OPEN, nullable=False
    )
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    job: Mapped["Job"] = relationship(back_populates="disputes")
    messages: Mapped[list["DisputeMessage"]] = relationship(back_populates="dispute")


class DisputeMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dispute_messages"
    __table_args__ = (Index("ix_dispute_messages_dispute_id", "dispute_id"),)

    dispute_id: Mapped[UUID] = mapped_column(ForeignKey("disputes.id", ondelete="RESTRICT"))
    sender_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    dispute: Mapped[Dispute] = relationship(back_populates="messages")