from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import ApplicationStatus, EmergencyLevel, NegotiationStatus


class ApplicationCreateRequest(BaseModel):
    proposed_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class CounterOfferRequest(BaseModel):
    proposed_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    message: str | None = Field(default=None, max_length=1000)


class NegotiationResponse(BaseModel):
    id: UUID
    proposed_amount: Decimal
    status: NegotiationStatus
    initiated_by: UUID
    message: str | None
    created_at: datetime


class ApplicationResponse(BaseModel):
    id: UUID
    job_id: UUID
    worker_id: UUID
    proposed_price: Decimal
    status: ApplicationStatus
    submitted_at: datetime
    withdrawn_at: datetime | None
    job_title: str
    job_category: str
    job_location: str
    job_description: str
    scheduled_date: date | None
    start_time: time | None
    end_time: time | None
    required_worker_count: int
    emergency_level: EmergencyLevel
    minimum_platform_cost: Decimal
    negotiations: list[NegotiationResponse]


class ApplicantResponse(BaseModel):
    id: UUID
    worker_id: UUID
    worker_name: str
    worker_rating: float | None
    worker_reliability: float | None
    worker_availability: str | None
    proposed_price: Decimal
    status: ApplicationStatus
    submitted_at: datetime
    skills: list[str]
    negotiations: list[NegotiationResponse]


class AgreementResponse(BaseModel):
    id: UUID
    job_id: UUID
    worker_id: UUID
    agreed_price: Decimal
    agreed_date: date
    start_time: time
    end_time: time
    worker_count: int
    status: str