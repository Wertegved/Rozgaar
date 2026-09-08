from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models.enums import NotificationType, UserRole
from app.db.models.notifications import Notification
from app.db.models.users import User
from app.providers.email import EmailConfigurationError, EmailMessageData, FakeEmailProvider, SMTPEmailProvider
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService


@pytest.fixture()
def notification_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    user = User(name="Recipient", phone="9990000001", email="recipient@example.test", role=UserRole.CONSUMER)
    session.add(user)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_all_phase15_notification_types_are_controlled() -> None:
    expected = {
        "COUNTER_OFFER_CREATED", "AGREEMENT_ACTIVE", "PAYMENT_FAILED", "JOB_COMPLETED",
        "REVIEW_CREATED", "COMPLAINT_CREATED", "COMPLAINT_STATUS_CHANGED",
        "JOB_CREATED", "JOB_STATUS_CHANGED", "SCHEDULE_UPDATED",
    }

    assert expected.issubset({item.value for item in NotificationType})


def test_fake_email_provider_has_isolated_inspectable_state() -> None:
    first = FakeEmailProvider()
    second = FakeEmailProvider()
    message = EmailMessageData("person@example.test", "Subject", "Body", "<p>Body</p>")

    assert first.send(message) is True
    assert first.sent == [message]
    assert second.sent == []


def test_smtp_provider_uses_fixed_configured_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "rozgaar@example.test")
    monkeypatch.setenv("SMTP_FROM_NAME", "Rozgaar")
    get_settings.cache_clear()
    sent: list[object] = []

    class FakeSMTP:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def __enter__(self) -> "FakeSMTP":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def starttls(self) -> None:
            pass

        def send_message(self, message: object) -> None:
            sent.append(message)

    monkeypatch.setattr("app.providers.email.smtplib.SMTP", FakeSMTP)
    assert SMTPEmailProvider().send(EmailMessageData("recipient@example.test", "Subject", "Body")) is True
    assert sent[0]["From"] == "Rozgaar <rozgaar@example.test>"
    get_settings.cache_clear()


def test_smtp_missing_required_configuration_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "")
    get_settings.cache_clear()

    with pytest.raises(EmailConfigurationError):
        SMTPEmailProvider().send(EmailMessageData("recipient@example.test", "Subject", "Body"))

    get_settings.cache_clear()


def test_notification_is_idempotent_and_duplicate_email_is_prevented(notification_session: Session) -> None:
    provider = FakeEmailProvider()
    service = NotificationService(EmailService(provider))
    user_id = notification_session.scalar(select(User.id))

    first = service.create_notification(
        notification_session, user_id, NotificationType.ACCOUNT_EVENT,
        "Account", "Account event", send_email=True, idempotency_key="account:1",
    )
    second = service.create_notification(
        notification_session, user_id, NotificationType.ACCOUNT_EVENT,
        "Account", "Account event", send_email=True, idempotency_key="account:1",
    )

    assert first.id == second.id
    assert notification_session.query(Notification).count() == 1
    assert len(provider.sent) == 1


def test_notification_service_does_not_commit_or_rollback(notification_session: Session) -> None:
    provider = FakeEmailProvider()
    service = NotificationService(EmailService(provider))
    user_id = notification_session.scalar(select(User.id))

    service.create_notification(
        notification_session, user_id, NotificationType.ACCOUNT_EVENT,
        "Pending", "Pending", send_email=False,
    )
    notification_session.rollback()

    assert notification_session.query(Notification).count() == 0


def test_email_failure_is_isolated_and_notification_persists(notification_session: Session) -> None:
    class FailingProvider:
        def send(self, _: EmailMessageData) -> bool:
            raise RuntimeError("provider unavailable")

    service = NotificationService(EmailService(FailingProvider()))
    user_id = notification_session.scalar(select(User.id))
    notification = service.create_notification(
        notification_session, user_id, NotificationType.ACCOUNT_EVENT,
        "Persisted", "Business event", send_email=True,
    )
    notification_session.commit()

    assert notification_session.get(Notification, notification.id) is not None
    assert service.email_service.last_error is not None


def test_invalid_email_provider_fails_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL_PROVIDER", "unknown")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="EMAIL_PROVIDER"):
        Settings(_env_file=None)

    get_settings.cache_clear()