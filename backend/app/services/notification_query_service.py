from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.models.enums import NotificationType
from app.db.models.notifications import Notification
from app.schemas.notifications import NotificationListResponse, NotificationResponse
from app.services.notification_service import NotificationService


def _response(item: Notification) -> NotificationResponse:
    return NotificationResponse.model_validate(item)


def list_notifications(session: Session, user_id: UUID, page: int, page_size: int, unread: bool | None, notification_type: NotificationType | None) -> NotificationListResponse:
    predicates = [Notification.recipient_user_id == user_id]
    if unread is not None:
        predicates.append(Notification.is_read == (not unread))
    if notification_type:
        predicates.append(Notification.notification_type == notification_type)
    total = session.scalar(select(func.count(Notification.id)).where(*predicates)) or 0
    items = session.scalars(select(Notification).where(*predicates).order_by(Notification.created_at.desc(), Notification.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return NotificationListResponse(items=[_response(item) for item in items], page=page, page_size=page_size, total=total)


def unread_count(session: Session, user_id: UUID) -> int:
    return session.scalar(select(func.count(Notification.id)).where(Notification.recipient_user_id == user_id, Notification.is_read.is_(False))) or 0


def mark_read(session: Session, user_id: UUID, notification_id: UUID) -> NotificationResponse:
    try:
        item = NotificationService().mark_as_read(session, user_id, notification_id)
        session.commit()
        return _response(item)
    except KeyError as error:
        raise APIError(404, "Notification not found") from error


def mark_all_read(session: Session, user_id: UUID) -> int:
    count = NotificationService().mark_all_as_read(session, user_id)
    session.commit()
    return count