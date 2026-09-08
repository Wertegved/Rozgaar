from datetime import date, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import EmergencyLevel, JobStatus


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("required_worker_count > 0", name="ck_jobs_worker_count_positive"),
        CheckConstraint("minimum_platform_cost >= 0", name="ck_jobs_cost_non_negative"),
        Index("ix_jobs_consumer_id", "consumer_id"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_scheduled_date", "scheduled_date"),
        Index("ix_jobs_category", "category"),
    )

    consumer_id: Mapped[UUID] = mapped_column(ForeignKey("consumer_profiles.id", ondelete="RESTRICT"))
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(500), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    required_worker_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    minimum_platform_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    emergency_level: Mapped[EmergencyLevel] = mapped_column(
        Enum(EmergencyLevel, name="emergency_level"), nullable=False
    )
    scheduled_date: Mapped[date | None] = mapped_column()
    start_time: Mapped[time | None] = mapped_column()
    end_time: Mapped[time | None] = mapped_column()
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.POSTED, nullable=False
    )

    consumer: Mapped["ConsumerProfile"] = relationship(back_populates="jobs")
    images: Mapped[list["JobImage"]] = relationship(back_populates="job")
    requirements: Mapped[list["JobRequirement"]] = relationship(back_populates="job")
    applications: Mapped[list["Application"]] = relationship(back_populates="job")
    negotiations: Mapped[list["Negotiation"]] = relationship(back_populates="job")
    agreements: Mapped[list["Agreement"]] = relationship(back_populates="job")
    payments: Mapped[list["Payment"]] = relationship(back_populates="job")
    completion: Mapped["Completion | None"] = relationship(back_populates="job")
    evidence: Mapped[list["CompletionEvidence"]] = relationship(back_populates="job")
    reviews: Mapped[list["Review"]] = relationship(back_populates="job")
    complaints: Mapped[list["Complaint"]] = relationship(back_populates="job")
    disputes: Mapped[list["Dispute"]] = relationship(back_populates="job")
    cancellations: Mapped[list["Cancellation"]] = relationship(back_populates="job")


class JobImage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_images"
    __table_args__ = (Index("ix_job_images_job_id", "job_id"),)

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    storage_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    job: Mapped[Job] = relationship(back_populates="images")


class JobRequirement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_requirements"
    __table_args__ = (Index("ix_job_requirements_job_id", "job_id"),)

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    skill_id: Mapped[UUID] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"))
    worker_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    job: Mapped[Job] = relationship(back_populates="requirements")
    skill: Mapped["Skill"] = relationship(back_populates="job_requirements")