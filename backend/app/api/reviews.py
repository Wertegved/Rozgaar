from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models.users import User
from app.db.session import get_db
from app.schemas.reviews import ReputationResponse, ReviewCreateRequest, ReviewListResponse, ReviewResponse
from app.services.review_service import create_review, list_job_reviews, my_reviews, reputation


router = APIRouter(tags=["reviews"])


@router.post("/jobs/{job_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def submit_review(
    job_id: UUID,
    data: ReviewCreateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ReviewResponse:
    return create_review(session, user, job_id, data)


@router.get("/jobs/{job_id}/reviews", response_model=list[ReviewResponse])
def get_job_reviews(
    job_id: UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[ReviewResponse]:
    return list_job_reviews(session, user, job_id)


@router.get("/users/{user_id}/reviews", response_model=ReputationResponse)
def get_user_reputation(
    user_id: UUID,
    _: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ReputationResponse:
    return reputation(session, user_id)


@router.get("/reviews/my", response_model=ReviewListResponse)
def get_my_reviews(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ReviewListResponse:
    return my_reviews(session, user, page, page_size)