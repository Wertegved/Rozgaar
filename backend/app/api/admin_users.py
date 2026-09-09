from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.db.models.applications import Application
from app.db.models.enums import AccountStatus, UserRole
from app.db.models.jobs import Job
from app.db.models.reviews import Review
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.db.session import get_db
from app.schemas.admin_users import AdminUserDetail, AdminUserListResponse, AdminUserSummary


router = APIRouter(prefix="/admin/users", tags=["admin users"])


def _summary(user: User, rating: float | None = None, reviews: int = 0, location: str | None = None) -> AdminUserSummary:
    return AdminUserSummary(
        id=user.id, name=user.name, phone=user.phone, email=user.email,
        role=user.role, account_status=user.account_status,
        rating_average=rating, review_count=reviews, working_location=location,
    )


@router.get("", response_model=AdminUserListResponse)
def list_users(
    role: UserRole | None = Query(None),
    account_status: AccountStatus | None = Query(None),
    search: str | None = Query(None, min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> AdminUserListResponse:
    statement = select(User).where(User.role.in_([UserRole.CONSUMER, UserRole.WORKER]))
    if role:
        statement = statement.where(User.role == role)
    if account_status:
        statement = statement.where(User.account_status == account_status)
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(or_(User.name.ilike(term), User.email.ilike(term), User.phone.ilike(term)))
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    users = session.scalars(statement.order_by(User.created_at.desc(), User.id).offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for user in users:
        reviews = session.scalar(select(func.count(Review.id)).where(Review.reviewed_user_id == user.id)) or 0
        rating = session.scalar(select(func.avg(Review.rating)).where(Review.reviewed_user_id == user.id))
        location = session.scalar(select(WorkerProfile.working_location).where(WorkerProfile.user_id == user.id))
        items.append(_summary(user, float(rating) if rating is not None else None, reviews, location))
    return AdminUserListResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/{user_id}", response_model=AdminUserDetail)
def user_detail(user_id: UUID, _: User = Depends(require_admin), session: Session = Depends(get_db)) -> AdminUserDetail:
    user = session.scalar(select(User).where(User.id == user_id, User.role.in_([UserRole.CONSUMER, UserRole.WORKER])))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    reviews = session.scalar(select(func.count(Review.id)).where(Review.reviewed_user_id == user.id)) or 0
    rating = session.scalar(select(func.avg(Review.rating)).where(Review.reviewed_user_id == user.id))
    worker = session.scalar(select(WorkerProfile).where(WorkerProfile.user_id == user.id))
    profile_id = worker.id if worker else session.scalar(select(ConsumerProfile.id).where(ConsumerProfile.user_id == user.id))
    jobs_count = session.scalar(select(func.count(Job.id)).join(ConsumerProfile, Job.consumer_id == ConsumerProfile.id).where(ConsumerProfile.user_id == user.id)) or 0
    applications_count = session.scalar(select(func.count(Application.id)).join(WorkerProfile, Application.worker_id == WorkerProfile.id).where(WorkerProfile.user_id == user.id)) or 0
    return AdminUserDetail(**_summary(user, float(rating) if rating is not None else None, reviews, worker.working_location if worker else None).model_dump(), profile_id=profile_id, jobs_count=jobs_count, applications_count=applications_count)
