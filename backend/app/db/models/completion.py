from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import EvidenceType


class Completion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "completions"
    __table_args__ = (Index("ix_completions_job_id", "job_id"),)

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), unique=True)
    worker_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumer_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    job: Mapped["Job"] = relationship(back_populates="completion")
    evidence: Mapped[list["CompletionEvidence"]] = relationship(back_populates="completion")


class CompletionEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "completion_evidence"
    __table_args__ = (
        Index("ix_completion_evidence_job_id", "job_id"),
        UniqueConstraint("job_id", "agreement_id", "uploaded_by", "evidence_type", name="uq_completion_evidence_submitter_type"),
    )

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    agreement_id: Mapped[UUID | None] = mapped_column(ForeignKey("agreements.id", ondelete="RESTRICT"))
    completion_id: Mapped[UUID | None] = mapped_column(ForeignKey("completions.id", ondelete="RESTRICT"))
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    uploader_role: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_type: Mapped[EvidenceType] = mapped_column(Enum(EvidenceType, name="evidence_type"), nullable=False)
    storage_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    job: Mapped["Job"] = relationship(back_populates="evidence")
    completion: Mapped["Completion | None"] = relationship(back_populates="evidence")


class CompletionWorkerState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "completion_worker_states"
    __table_args__ = (
        UniqueConstraint("job_id", "agreement_id", name="uq_completion_worker_state_agreement"),
        Index("ix_completion_worker_states_job_id", "job_id"),
    )

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False)
    agreement_id: Mapped[UUID] = mapped_column(ForeignKey("agreements.id", ondelete="RESTRICT"), nullable=False)
    worker_id: Mapped[UUID] = mapped_column(ForeignKey("worker_profiles.id", ondelete="RESTRICT"), nullable=False)
    worker_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))