from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.enums import AvailabilityStatus, AgreementStatus


class AvailabilityCreateRequest(BaseModel):
    available_date: date
    start_time: time
    end_time: time
    status: AvailabilityStatus = AvailabilityStatus.AVAILABLE

    @model_validator(mode="after")
    def validate_time_order(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    available_date: date
    start_time: time
    end_time: time
    status: AvailabilityStatus
    created_at: datetime
    updated_at: datetime


class ScheduleResponse(BaseModel):
    agreement_id: UUID
    job_id: UUID
    job_title: str
    job_category: str
    scheduled_date: date
    start_time: time
    end_time: time
    status: AgreementStatus


class JobScheduleResponse(BaseModel):
    agreement_id: UUID
    job_id: UUID
    worker_id: UUID
    worker_name: str
    scheduled_date: date
    start_time: time
    end_time: time
    status: AgreementStatus