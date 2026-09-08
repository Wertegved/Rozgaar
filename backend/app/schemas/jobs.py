from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models.enums import EmergencyLevel, JobStatus


class JobImageMetadataInput(BaseModel):
    storage_bucket: str = Field(min_length=1, max_length=100)
    storage_path: str = Field(min_length=1, max_length=500)

    @field_validator("storage_path")
    @classmethod
    def reject_unsafe_storage_path(cls, value: str) -> str:
        value = value.strip()
        if not value or value.startswith("/") or ".." in value or "://" in value:
            raise ValueError("storage_path must be a relative private object path")
        return value


class JobCreateRequest(BaseModel):
    category: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    location: str = Field(min_length=1, max_length=500)
    required_worker_count: int = Field(default=1, gt=0)
    minimum_platform_cost: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    emergency_level: EmergencyLevel
    scheduled_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    required_skill_ids: list[UUID] = Field(default_factory=list)
    images: list[JobImageMetadataInput] = Field(default_factory=list)

    @field_validator("category", "title", "description", "location")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("required_skill_ids")
    @classmethod
    def reject_duplicate_skills(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("required skills must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_time_range(self):
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("start_time and end_time must be provided together")
        if self.start_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class JobUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str | None = Field(default=None, min_length=1, max_length=120)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1, max_length=500)
    required_worker_count: int | None = Field(default=None, gt=0)
    minimum_platform_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    emergency_level: EmergencyLevel | None = None
    scheduled_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None

    @field_validator("category", "title", "description", "location")
    @classmethod
    def reject_blank_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_update_time_range(self):
        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class JobListQuery(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=120)
    emergency_level: EmergencyLevel | None = None
    scheduled_date: date | None = None
    location: str | None = Field(default=None, min_length=1, max_length=500)
    min_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    max_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    required_worker_count: int | None = Field(default=None, gt=0)
    status: JobStatus | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_price_range(self):
        if self.min_price is not None and self.max_price is not None and self.max_price < self.min_price:
            raise ValueError("max_price must be greater than or equal to min_price")
        return self


class SkillResponse(BaseModel):
    id: UUID
    name: str


class JobImageResponse(BaseModel):
    id: UUID
    storage_bucket: str
    storage_path: str


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    title: str
    description: str
    location: str
    latitude: float | None
    longitude: float | None
    required_worker_count: int
    minimum_platform_cost: Decimal
    emergency_level: EmergencyLevel
    scheduled_date: date | None
    start_time: time | None
    end_time: time | None
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    required_skills: list[SkillResponse]
    images: list[JobImageResponse]


class PaginatedJobsResponse(BaseModel):
    items: list[JobResponse]
    page: int
    page_size: int
    total: int
    pages: int