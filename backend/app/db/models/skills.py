from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Skill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    worker_skills: Mapped[list["WorkerSkill"]] = relationship(back_populates="skill")
    job_requirements: Mapped[list["JobRequirement"]] = relationship(back_populates="skill")