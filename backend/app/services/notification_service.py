from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.enums import NotificationType
from app.db.models.notifications import Notification
from app.db.models.users import User
from app.services.email_service import EmailService


class NotificationService:
    def __init__(self, email_service: EmailService | None = None) -> None:
        self.email_service = email_service or EmailService()

    def create_notification(
        self, session: Session, recipient_user_id: UUID, notification_type: NotificationType,
        title: str, message: str, related_entity_type: str | None = None,
        related_entity_id: UUID | None = None, send_email: bool = True,
        idempotency_key: str | None = None,
    ) -> Notification:
        if not isinstance(notification_type, NotificationType):
            raise ValueError("notification_type must be a NotificationType")
        if idempotency_key is not None:
            existing = session.scalar(
                select(Notification).where(
                    Notification.recipient_user_id == recipient_user_id,
                    Notification.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return existing

        item = Notification(
            recipient_user_id=recipient_user_id, notification_type=notification_type,
            title=title, message=message, related_entity_type=related_entity_type,
            related_entity_id=related_entity_id, idempotency_key=idempotency_key,
        )
        if idempotency_key is None:
            session.add(item)
            session.flush()
        else:
            try:
                with session.begin_nested():
                    session.add(item)
                    session.flush()
            except IntegrityError:
                existing = session.scalar(
                    select(Notification).where(
                        Notification.recipient_user_id == recipient_user_id,
                        Notification.idempotency_key == idempotency_key,
                    )
                )
                if existing is None:
                    raise
                return existing
        if send_email:
            recipient = session.scalar(select(User.email).where(User.id == recipient_user_id))
            self.email_service.send(recipient, title, message)
        return item

    def mark_as_read(self, session: Session, user_id: UUID, notification_id: UUID) -> Notification:
        item = session.scalar(select(Notification).where(Notification.id == notification_id, Notification.recipient_user_id == user_id))
        if item is None:
            raise KeyError("notification not found")
        item.is_read = True
        item.read_at = datetime.now(timezone.utc)
        session.flush()
        return item

    def mark_all_as_read(self, session: Session, user_id: UUID) -> int:
        items = session.scalars(select(Notification).where(Notification.recipient_user_id == user_id, Notification.is_read.is_(False))).all()
        now = datetime.now(timezone.utc)
        for item in items:
            item.is_read = True
            item.read_at = now
        session.flush()
        return len(items)