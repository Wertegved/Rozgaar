from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.enums import ComplaintCategory, ComplaintStatus, DisputeStatus


class ComplaintCreateRequest(BaseModel):
    job_id: UUID | None = None
    category: ComplaintCategory
    message: str = Field(min_length=1, max_length=5000)


class ComplaintStatusRequest(BaseModel):
    status: ComplaintStatus


class AdminResponseRequest(BaseModel):
    response: str = Field(min_length=1, max_length=5000)


class ComplaintResponse(BaseModel):
    id: UUID
    job_id: UUID | None
    raised_by: UUID
    reporter_role: str
    category: ComplaintCategory
    message: str
    status: ComplaintStatus
    resolution: str | None
    created_at: datetime
    updated_at: datetime


class ComplaintListResponse(BaseModel):
    items: list[ComplaintResponse]
    page: int
    page_size: int
    total: int


class DisputeCreateRequest(BaseModel):
    category: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=5000)


class DisputeStatusRequest(BaseModel):
    status: DisputeStatus


class DisputeResolutionRequest(BaseModel):
    resolution: str = Field(min_length=1, max_length=5000)


class DisputeResponse(BaseModel):
    id: UUID
    job_id: UUID
    raised_by: UUID
    category: str
    description: str
    status: DisputeStatus
    resolution: str | None
    created_at: datetime
    updated_at: datetime


class DisputeContextResponse(DisputeResponse):
    job_title: str
    job_status: str
    consumer_id: UUID
    worker_ids: list[UUID]
    agreement_ids: list[UUID]
    payment_statuses: list[str]
    completion_evidence_ids: list[UUID]
    review_ids: list[UUID]