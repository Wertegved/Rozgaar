from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import AccountStatus, UserRole


class AdminUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    email: str | None
    role: UserRole
    account_status: AccountStatus
    rating_average: float | None = None
    review_count: int = 0
    working_location: str | None = None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserSummary]
    page: int
    page_size: int
    total: int


class AdminUserDetail(AdminUserSummary):
    profile_id: UUID | None = None
    jobs_count: int = 0
    applications_count: int = 0
