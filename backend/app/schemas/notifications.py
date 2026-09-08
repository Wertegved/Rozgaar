from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models.enums import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    notification_type: NotificationType
    title: str
    message: str
    related_entity_type: str | None
    related_entity_id: UUID | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    page: int
    page_size: int
    total: int