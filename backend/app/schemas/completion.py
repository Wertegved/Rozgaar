from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CompletionSubmitRequest(BaseModel):
    storage_path: str = Field(min_length=1, max_length=500)
    storage_bucket: str = Field(default="completion-evidence", min_length=1, max_length=100)

    @field_validator("storage_path")
    @classmethod
    def reject_unsafe_storage_path(cls, value: str) -> str:
        value = value.strip()
        if not value or value.startswith("/") or ".." in value or "://" in value:
            raise ValueError("storage_path must be a relative private object path")
        return value


class CompletionResponse(BaseModel):
    job_id: UUID
    worker_evidence: bool
    worker_confirmed: bool
    consumer_evidence: bool
    consumer_confirmed: bool
    final_payment_completed: bool
    job_completed: bool
    evidence_ids: list[UUID]
    updated_at: datetime | None


class CompletionEvidenceUploadResponse(BaseModel):
    storage_bucket: str
    storage_path: str
    filename: str
    size_bytes: int