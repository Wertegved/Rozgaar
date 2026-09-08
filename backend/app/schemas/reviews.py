from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ReviewCreateRequest(BaseModel):
    reviewed_user_id: UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewResponse(BaseModel):
    id: UUID
    job_id: UUID
    reviewer_id: UUID
    reviewed_user_id: UUID
    rating: int
    comment: str | None
    created_at: datetime
    updated_at: datetime


class ReputationResponse(BaseModel):
    user_id: UUID
    average_rating: float | None
    total_reviews: int
    rating_distribution: dict[str, int]
    reviews: list[ReviewResponse]


class ReviewListResponse(BaseModel):
    items: list[ReviewResponse]
    page: int
    page_size: int
    total: int