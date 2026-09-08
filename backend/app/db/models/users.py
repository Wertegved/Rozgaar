from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.enums import AccountStatus, UserRole
from app.db.models.reviews import Review


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_role", "role"),)

    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    account_status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status"), default=AccountStatus.ACTIVE, nullable=False
    )

    consumer_profile: Mapped["ConsumerProfile | None"] = relationship(back_populates="user")
    worker_profile: Mapped["WorkerProfile | None"] = relationship(back_populates="user")
    reviews_received: Mapped[list[Review]] = relationship(foreign_keys=[Review.reviewed_user_id], viewonly=True)


class ConsumerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "consumer_profiles"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True)
    user: Mapped[User] = relationship(back_populates="consumer_profile")
    jobs: Mapped[list["Job"]] = relationship(back_populates="consumer")


class WorkerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "worker_profiles"
    __table_args__ = (
        CheckConstraint("working_radius_km IS NULL OR working_radius_km >= 0", name="ck_worker_radius_non_negative"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True)
    working_location: Mapped[str | None] = mapped_column(String(255))
    working_radius_km: Mapped[int | None] = mapped_column()
    working_latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    working_longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    availability: Mapped[str | None] = mapped_column(String(255))
    areas_served: Mapped[str | None] = mapped_column(String(500))
    rating_average: Mapped[float | None] = mapped_column()
    reliability_score: Mapped[float | None] = mapped_column()
    user: Mapped[User] = relationship(back_populates="worker_profile")
    skills: Mapped[list["WorkerSkill"]] = relationship(back_populates="worker")


class WorkerSkill(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "worker_skills"
    __table_args__ = (
        UniqueConstraint("worker_id", "skill_id", name="uq_worker_skills_worker_skill"),
        Index("ix_worker_skills_worker_id", "worker_id"),
    )

    worker_id: Mapped[UUID] = mapped_column(ForeignKey("worker_profiles.id", ondelete="RESTRICT"))
    skill_id: Mapped[UUID] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"))
    worker: Mapped[WorkerProfile] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(back_populates="worker_skills")