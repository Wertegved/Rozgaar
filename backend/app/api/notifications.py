from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models.enums import NotificationType
from app.db.models.users import User
from app.db.session import get_db
from app.schemas.notifications import NotificationListResponse, NotificationResponse
from app.services.notification_query_service import list_notifications, mark_all_read, mark_read, unread_count


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def notifications(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), unread: bool | None = None, notification_type: NotificationType | None = None, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> NotificationListResponse:
    return list_notifications(session, user.id, page, page_size, unread, notification_type)


@router.get("/unread-count")
def notification_unread_count(user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> dict[str, int]:
    return {"count": unread_count(session, user.id)}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(notification_id: UUID, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> NotificationResponse:
    return mark_read(session, user.id, notification_id)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_notifications_read(user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> None:
    mark_all_read(session, user.id)