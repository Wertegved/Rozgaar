from collections.abc import Generator
from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.hashing import hash_password
from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.db.base import Base
from app.db.models.agreements import Agreement
from app.db.models.enums import AccountStatus, AgreementStatus, ComplaintCategory, DisputeStatus, EmergencyLevel, JobStatus, NotificationType, UserRole
from app.db.models.jobs import Job
from app.db.models.notifications import Notification
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.db.session import get_db
from app.main import app
from app.providers.email import EmailMessageData, FakeEmailProvider, SMTPEmailProvider
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService


@pytest.fixture()
def notification_context(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, object], None, None]:
    monkeypatch.setenv("JWT_SECRET_KEY", "phase-thirteen-test-secret-key-32-bytes-long")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    user = User(name="User", phone="9800000001", email="user13@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    other = User(name="Other", phone="9800000002", email="other13@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    session.add_all([user, other])
    session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        request_session = factory()
        try:
            yield request_session
        finally:
            request_session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield {"client": client, "factory": factory, "user": user, "other": other}
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


@pytest.fixture()
def phase13_context(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, object], None, None]:
    monkeypatch.setenv("JWT_SECRET_KEY", "phase-thirteen-routing-test-secret-key")
    monkeypatch.setenv("PAYMENT_PROVIDER", "simulated")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    consumer = User(name="Consumer", phone="9810000001", email="consumer-routing@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    worker = User(name="Worker", phone="9810000002", email="worker-routing@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    unrelated = User(name="Unrelated", phone="9810000003", email="unrelated-routing@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    admin = User(name="Admin", phone="9810000004", email="admin-routing@example.com", password_hash=hash_password("password123"), role=UserRole.ADMIN, account_status=AccountStatus.ACTIVE)
    session.add_all([consumer, worker, unrelated, admin])
    session.flush()
    consumer_profile = ConsumerProfile(user_id=consumer.id)
    worker_profile = WorkerProfile(user_id=worker.id)
    job = Job(consumer=consumer_profile, category="painting", title="Routing job", description="Paint", location="Mumbai", required_worker_count=1, minimum_platform_cost=Decimal("1000"), emergency_level=EmergencyLevel.RELAXED, scheduled_date=date.today(), start_time=time(10), end_time=time(12), status=JobStatus.ACCEPTED)
    application_job = Job(consumer=consumer_profile, category="painting", title="Application routing job", description="Paint", location="Mumbai", required_worker_count=1, minimum_platform_cost=Decimal("1000"), emergency_level=EmergencyLevel.RELAXED, scheduled_date=date.today(), start_time=time(13), end_time=time(15), status=JobStatus.POSTED)
    agreement = Agreement(job=job, worker=worker_profile, agreed_price=Decimal("1000"), agreed_date=date.today(), start_time=time(10), end_time=time(12), worker_count=1, status=AgreementStatus.ACTIVE)
    session.add_all([consumer_profile, worker_profile, job, application_job, agreement])
    session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        request_session = factory()
        try:
            yield request_session
        finally:
            request_session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield {"client": client, "factory": factory, "consumer": consumer, "worker": worker, "unrelated": unrelated, "admin": admin, "job": job, "application_job": application_job, "agreement": agreement}
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def phase13_recipients(context: dict[str, object], notification_type: NotificationType) -> set[object]:
    session = context["factory"]()
    recipients = set(session.scalars(select(Notification.recipient_user_id).where(Notification.notification_type == notification_type)))
    session.close()
    return recipients


def assert_phase13_recipients(context: dict[str, object], notification_type: NotificationType, *users: User) -> None:
    assert phase13_recipients(context, notification_type) == {user.id for user in users}


def application(context: dict[str, object]) -> dict[str, object]:
    response = context["client"].post(f"/api/v1/jobs/{context['application_job'].id}/applications", headers=auth(context["worker"]), json={"proposed_price": "1000"})
    assert response.status_code == 201
    return response.json()


def test_phase13_notification_pagination_has_correct_size_and_boundaries(notification_context: dict[str, object]) -> None:
    session = notification_context["factory"]()
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    notifications = [
        Notification(
            id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
            recipient_user_id=notification_context["user"].id,
            notification_type=NotificationType.ACCOUNT_EVENT,
            title=f"Notification {index}", message="Page test", created_at=created_at,
        )
        for index in range(1, 6)
    ]
    session.add_all(notifications)
    session.commit()
    session.close()

    client = notification_context["client"]
    pages = [
        client.get(f"/api/v1/notifications?page={page}&page_size=2", headers=auth(notification_context["user"]))
        for page in (1, 2, 3)
    ]
    assert [response.status_code for response in pages] == [200, 200, 200]
    bodies = [response.json() for response in pages]
    assert [len(body["items"]) for body in bodies] == [2, 2, 1]
    assert all(body["total"] == 5 for body in bodies)
    ids_by_page = [[item["id"] for item in body["items"]] for body in bodies]
    assert len(set().union(*[set(ids) for ids in ids_by_page])) == 5
    assert set(ids_by_page[0]).isdisjoint(ids_by_page[1])
    assert set(ids_by_page[1]).isdisjoint(ids_by_page[2])


def test_phase13_equal_created_at_uses_id_tiebreaker_without_skips(notification_context: dict[str, object]) -> None:
    session = notification_context["factory"]()
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ids = [UUID(f"00000000-0000-0000-0000-{index:012d}") for index in (1, 2, 3)]
    session.add_all([
        Notification(
            id=notification_id,
            recipient_user_id=notification_context["user"].id,
            notification_type=NotificationType.ACCOUNT_EVENT,
            title="Equal timestamp", message="Tie-breaker test", created_at=created_at,
        )
        for notification_id in ids
    ])
    session.commit()
    session.close()

    client = notification_context["client"]
    pages = [
        client.get(f"/api/v1/notifications?page={page}&page_size=1", headers=auth(notification_context["user"])).json()["items"][0]["id"]
        for page in (1, 2, 3)
    ]
    assert pages == [str(ids[2]), str(ids[1]), str(ids[0])]
    assert len(set(pages)) == 3


def test_phase13_unread_filter_count_empty_results_and_user_isolation(notification_context: dict[str, object]) -> None:
    session = notification_context["factory"]()
    session.add_all([
        Notification(recipient_user_id=notification_context["user"].id, notification_type=NotificationType.ACCOUNT_EVENT, title="Unread one", message="Unread"),
        Notification(recipient_user_id=notification_context["user"].id, notification_type=NotificationType.ACCOUNT_EVENT, title="Unread two", message="Unread"),
        Notification(recipient_user_id=notification_context["user"].id, notification_type=NotificationType.ACCOUNT_EVENT, title="Read", message="Read", is_read=True),
        Notification(recipient_user_id=notification_context["other"].id, notification_type=NotificationType.ACCOUNT_EVENT, title="Other unread", message="Other"),
    ])
    session.commit()
    session.close()

    client = notification_context["client"]
    user_headers = auth(notification_context["user"])
    other_headers = auth(notification_context["other"])
    unread = client.get("/api/v1/notifications?unread=true&page_size=1", headers=user_headers).json()
    assert unread["total"] == 2
    assert len(unread["items"]) == 1
    assert client.get("/api/v1/notifications/unread-count", headers=user_headers).json() == {"count": 2}
    assert client.get("/api/v1/notifications?unread=false", headers=user_headers).json()["total"] == 1
    assert client.get("/api/v1/notifications/unread-count", headers=other_headers).json() == {"count": 1}
    assert client.get("/api/v1/notifications?page=1&page_size=20", headers=other_headers).json()["total"] == 1

    empty = client.get("/api/v1/notifications?notification_type=APPLICATION_SUBMITTED", headers=user_headers)
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "page": 1, "page_size": 20, "total": 0}


def test_phase13_application_submitted_notifies_consumer_only(phase13_context: dict[str, object]) -> None:
    application(phase13_context)
    assert_phase13_recipients(phase13_context, NotificationType.APPLICATION_SUBMITTED, phase13_context["consumer"])


def test_phase13_application_accepted_notifies_accepted_worker(phase13_context: dict[str, object]) -> None:
    item = application(phase13_context)
    response = phase13_context["client"].post(f"/api/v1/applications/{item['id']}/accept", headers=auth(phase13_context["consumer"]))
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.APPLICATION_ACCEPTED, phase13_context["worker"])


def test_phase13_application_rejected_notifies_rejected_worker(phase13_context: dict[str, object]) -> None:
    item = application(phase13_context)
    response = phase13_context["client"].post(f"/api/v1/applications/{item['id']}/reject", headers=auth(phase13_context["consumer"]))
    assert response.status_code == 204
    assert_phase13_recipients(phase13_context, NotificationType.APPLICATION_REJECTED, phase13_context["worker"])


def test_phase13_application_withdrawn_notifies_consumer(phase13_context: dict[str, object]) -> None:
    item = application(phase13_context)
    response = phase13_context["client"].post(f"/api/v1/applications/{item['id']}/withdraw", headers=auth(phase13_context["worker"]))
    assert response.status_code == 204
    assert_phase13_recipients(phase13_context, NotificationType.APPLICATION_WITHDRAWN, phase13_context["consumer"])


def test_phase13_worker_counter_offer_ignores_requested_recipient(phase13_context: dict[str, object]) -> None:
    item = application(phase13_context)
    response = phase13_context["client"].post(f"/api/v1/applications/{item['id']}/counter-offer", headers=auth(phase13_context["worker"]), json={"proposed_amount": "1100", "message": "More time", "recipient_user_id": str(phase13_context["unrelated"].id)})
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.COUNTER_OFFER_RECEIVED, phase13_context["consumer"])


def test_phase13_consumer_counter_offer_notifies_worker(phase13_context: dict[str, object]) -> None:
    item = application(phase13_context)
    response = phase13_context["client"].post(f"/api/v1/applications/{item['id']}/counter-offer", headers=auth(phase13_context["consumer"]), json={"proposed_amount": "1100"})
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.COUNTER_OFFER_RECEIVED, phase13_context["worker"])


def test_phase13_counter_offer_accepted_notifies_both_parties(phase13_context: dict[str, object]) -> None:
    item = application(phase13_context)
    counter = phase13_context["client"].post(f"/api/v1/applications/{item['id']}/counter-offer", headers=auth(phase13_context["consumer"]), json={"proposed_amount": "1100"}).json()
    response = phase13_context["client"].post(f"/api/v1/negotiations/{counter['id']}/accept", headers=auth(phase13_context["worker"]))
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.COUNTER_OFFER_ACCEPTED, phase13_context["consumer"], phase13_context["worker"])


def test_phase13_counter_offer_rejected_notifies_both_parties(phase13_context: dict[str, object]) -> None:
    item = application(phase13_context)
    counter = phase13_context["client"].post(f"/api/v1/applications/{item['id']}/counter-offer", headers=auth(phase13_context["consumer"]), json={"proposed_amount": "1100"}).json()
    response = phase13_context["client"].post(f"/api/v1/negotiations/{counter['id']}/reject", headers=auth(phase13_context["worker"]))
    assert response.status_code == 204
    assert_phase13_recipients(phase13_context, NotificationType.COUNTER_OFFER_REJECTED, phase13_context["consumer"], phase13_context["worker"])


def test_phase13_agreement_created_notifies_consumer_and_worker(phase13_context: dict[str, object]) -> None:
    item = application(phase13_context)
    response = phase13_context["client"].post(f"/api/v1/applications/{item['id']}/accept", headers=auth(phase13_context["consumer"]))
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.AGREEMENT_CREATED, phase13_context["consumer"], phase13_context["worker"])


def test_phase13_advance_payment_notifies_relevant_parties_only(phase13_context: dict[str, object]) -> None:
    response = phase13_context["client"].post(f"/api/v1/agreements/{phase13_context['agreement'].id}/payments/advance", headers=auth(phase13_context["consumer"]))
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.ADVANCE_PAYMENT_COMPLETED, phase13_context["consumer"], phase13_context["worker"])


def test_phase13_worker_completion_notifies_consumer(phase13_context: dict[str, object]) -> None:
    response = phase13_context["client"].post(f"/api/v1/jobs/{phase13_context['job'].id}/completion/worker", headers=auth(phase13_context["worker"]), json={"storage_bucket": "completion-evidence", "storage_path": "worker/done.jpg"})
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.COMPLETION_CONFIRMED, phase13_context["consumer"])


def test_phase13_consumer_completion_notifies_worker(phase13_context: dict[str, object]) -> None:
    response = phase13_context["client"].post(f"/api/v1/jobs/{phase13_context['job'].id}/completion/consumer", headers=auth(phase13_context["consumer"]), json={"storage_bucket": "completion-evidence", "storage_path": "consumer/done.jpg"})
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.COMPLETION_CONFIRMED, phase13_context["worker"])


def test_phase13_final_payment_notifies_consumer_and_worker(phase13_context: dict[str, object]) -> None:
    from app.services.payment_service import pay_advance, release_final_payment

    session = phase13_context["factory"]()
    consumer = session.get(User, phase13_context["consumer"].id)
    pay_advance(session, consumer, phase13_context["agreement"].id)
    release_final_payment(session, phase13_context["agreement"].id)
    session.close()
    assert_phase13_recipients(phase13_context, NotificationType.FINAL_PAYMENT_COMPLETED, phase13_context["consumer"], phase13_context["worker"])


def test_phase13_review_available_notifies_user_who_must_review(phase13_context: dict[str, object]) -> None:
    session = phase13_context["factory"]()
    session.get(Job, phase13_context["job"].id).status = JobStatus.COMPLETED
    session.commit()
    session.close()
    response = phase13_context["client"].post(f"/api/v1/jobs/{phase13_context['job'].id}/reviews", headers=auth(phase13_context["consumer"]), json={"reviewed_user_id": str(phase13_context["worker"].id), "rating": 5})
    assert response.status_code == 201
    assert_phase13_recipients(phase13_context, NotificationType.REVIEW_AVAILABLE, phase13_context["worker"])


def test_phase13_review_request_cannot_choose_unrelated_recipient(phase13_context: dict[str, object]) -> None:
    session = phase13_context["factory"]()
    session.get(Job, phase13_context["job"].id).status = JobStatus.COMPLETED
    session.commit()
    session.close()
    response = phase13_context["client"].post(f"/api/v1/jobs/{phase13_context['job'].id}/reviews", headers=auth(phase13_context["consumer"]), json={"reviewed_user_id": str(phase13_context["unrelated"].id), "rating": 5})
    assert response.status_code == 403
    assert phase13_recipients(phase13_context, NotificationType.REVIEW_AVAILABLE) == set()


def test_phase13_complaint_response_notifies_reporter(phase13_context: dict[str, object]) -> None:
    client = phase13_context["client"]
    complaint = client.post("/api/v1/complaints", headers=auth(phase13_context["consumer"]), json={"category": ComplaintCategory.GENERAL, "message": "Please respond"}).json()
    response = client.post(f"/api/v1/admin/complaints/{complaint['id']}/response", headers=auth(phase13_context["admin"]), json={"response": "Responded"})
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.COMPLAINT_RESPONSE, phase13_context["consumer"])


def test_phase13_dispute_created_notifies_participants_and_admins(phase13_context: dict[str, object]) -> None:
    response = phase13_context["client"].post(f"/api/v1/jobs/{phase13_context['job'].id}/disputes", headers=auth(phase13_context["consumer"]), json={"category": "JOB_ISSUE", "description": "Please investigate"})
    assert response.status_code == 201
    assert_phase13_recipients(phase13_context, NotificationType.DISPUTE_CREATED, phase13_context["consumer"], phase13_context["worker"], phase13_context["admin"])


def test_phase13_dispute_status_changed_notifies_participants_and_admins(phase13_context: dict[str, object]) -> None:
    client = phase13_context["client"]
    dispute = client.post(f"/api/v1/jobs/{phase13_context['job'].id}/disputes", headers=auth(phase13_context["consumer"]), json={"category": "JOB_ISSUE", "description": "Please investigate"}).json()
    response = client.patch(f"/api/v1/admin/disputes/{dispute['id']}/status", headers=auth(phase13_context["admin"]), json={"status": DisputeStatus.UNDER_REVIEW})
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.DISPUTE_STATUS_CHANGED, phase13_context["consumer"], phase13_context["worker"], phase13_context["admin"])


def test_phase13_dispute_resolved_notifies_participants_and_admins(phase13_context: dict[str, object]) -> None:
    client = phase13_context["client"]
    dispute = client.post(f"/api/v1/jobs/{phase13_context['job'].id}/disputes", headers=auth(phase13_context["consumer"]), json={"category": "JOB_ISSUE", "description": "Please investigate"}).json()
    response = client.post(f"/api/v1/admin/disputes/{dispute['id']}/resolve", headers=auth(phase13_context["admin"]), json={"resolution": "Resolved"})
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.DISPUTE_RESOLVED, phase13_context["consumer"], phase13_context["worker"], phase13_context["admin"])


def test_notification_inbox_read_state_and_idor(notification_context: dict[str, object]) -> None:
    session = notification_context["factory"]()
    fake = FakeEmailProvider()
    NotificationService(EmailService(fake)).create_notification(session, notification_context["user"].id, NotificationType.ACCOUNT_EVENT, "Account event", "Welcome", send_email=True)
    session.commit()
    session.close()
    client = notification_context["client"]
    user = notification_context["user"]
    other = notification_context["other"]
    listed = client.get("/api/v1/notifications", headers=auth(user))
    assert listed.status_code == 200
    notification_id = listed.json()["items"][0]["id"]
    assert client.get("/api/v1/notifications/unread-count", headers=auth(user)).json()["count"] == 1
    assert client.post(f"/api/v1/notifications/{notification_id}/read", headers=auth(other)).status_code == 404
    assert client.post(f"/api/v1/notifications/{notification_id}/read", headers=auth(user)).status_code == 200
    assert client.get("/api/v1/notifications/unread-count", headers=auth(user)).json()["count"] == 0
    assert fake.sent[0].recipient == "user13@example.com"


def test_mark_all_read_and_fake_provider_sender_configuration(notification_context: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    session = notification_context["factory"]()
    service = NotificationService(EmailService(FakeEmailProvider()))
    service.create_notification(session, notification_context["user"].id, NotificationType.ACCOUNT_EVENT, "One", "First", send_email=False)
    service.create_notification(session, notification_context["user"].id, NotificationType.ACCOUNT_EVENT, "Two", "Second", send_email=False)
    session.close()
    response = notification_context["client"].post("/api/v1/notifications/read-all", headers=auth(notification_context["user"]))
    assert response.status_code == 204
    monkeypatch.setenv("EMAIL_PROVIDER", "fake")
    get_settings.cache_clear()
    assert EmailService().provider.__class__ is FakeEmailProvider


def test_notification_service_respects_caller_commit_and_rollback(notification_context: dict[str, object]) -> None:
    session = notification_context["factory"]()
    service = NotificationService(EmailService(FakeEmailProvider()))
    service.create_notification(session, notification_context["user"].id, NotificationType.ACCOUNT_EVENT, "Pending", "Not committed", send_email=False)
    session.rollback()
    session.close()

    session = notification_context["factory"]()
    service.create_notification(session, notification_context["user"].id, NotificationType.ACCOUNT_EVENT, "Committed", "Persisted", send_email=False)
    session.commit()
    session.close()
    response = notification_context["client"].get("/api/v1/notifications", headers=auth(notification_context["user"]))
    assert response.json()["total"] == 1


def test_email_provider_selection_and_fake_state_are_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL_PROVIDER", "fake")
    get_settings.cache_clear()
    first = FakeEmailProvider()
    second = FakeEmailProvider()
    first.send(__import__("app.providers.email", fromlist=["EmailMessageData"]).EmailMessageData("a@example.com", "A", "A"))
    assert len(first.sent) == 1
    assert second.sent == []
    monkeypatch.setenv("EMAIL_PROVIDER", "invalid")
    get_settings.cache_clear()
    with pytest.raises(ValueError):
        EmailService()


class FailingEmailProvider:
    def send(self, message: EmailMessageData) -> bool:
        raise RuntimeError("SMTP unavailable")


def test_phase13_email_failure_does_not_rollback_business_transaction(notification_context: dict[str, object]) -> None:
    session = notification_context["factory"]()
    notification = NotificationService(EmailService(FailingEmailProvider())).create_notification(
        session, notification_context["user"].id, NotificationType.ACCOUNT_EVENT, "Business event", "Persist this event"
    )
    session.commit()
    session.close()

    session = notification_context["factory"]()
    persisted = session.get(Notification, notification.id)
    assert persisted is not None
    session.close()


def test_phase13_same_event_and_recipient_is_idempotent(notification_context: dict[str, object]) -> None:
    session = notification_context["factory"]()
    service = NotificationService(EmailService(FakeEmailProvider()))
    first = service.create_notification(
        session, notification_context["user"].id, NotificationType.ACCOUNT_EVENT,
        "Event", "First", idempotency_key="event-1",
    )
    second = service.create_notification(
        session, notification_context["user"].id, NotificationType.ACCOUNT_EVENT,
        "Event changed", "Retry", idempotency_key="event-1",
    )
    session.commit()
    assert first.id == second.id
    assert len(session.scalars(select(Notification).where(Notification.idempotency_key == "event-1")).all()) == 1
    session.close()


def test_phase13_idempotency_allows_different_recipients_and_events(notification_context: dict[str, object]) -> None:
    session = notification_context["factory"]()
    service = NotificationService(EmailService(FakeEmailProvider()))
    first = service.create_notification(
        session, notification_context["user"].id, NotificationType.ACCOUNT_EVENT,
        "Event", "User event", idempotency_key="event-1",
    )
    other_recipient = service.create_notification(
        session, notification_context["other"].id, NotificationType.ACCOUNT_EVENT,
        "Event", "Other user event", idempotency_key="event-1",
    )
    different_event = service.create_notification(
        session, notification_context["user"].id, NotificationType.ACCOUNT_EVENT,
        "Event", "Second event", idempotency_key="event-2",
    )
    session.commit()
    assert {first.recipient_user_id, other_recipient.recipient_user_id} == {notification_context["user"].id, notification_context["other"].id}
    assert different_event.id != first.id
    assert len(session.scalars(select(Notification)).all()) == 3
    session.close()


def test_phase13_missing_smtp_keeps_business_operation_and_in_app_notification(notification_context: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "")
    get_settings.cache_clear()
    response = notification_context["client"].post(
        f"/api/v1/notifications/read-all", headers=auth(notification_context["user"])
    )
    assert response.status_code == 204

    session = notification_context["factory"]()
    service = NotificationService()
    service.create_notification(session, notification_context["user"].id, NotificationType.ACCOUNT_EVENT, "In app", "SMTP is optional")
    session.commit()
    assert session.scalar(select(Notification.id).where(Notification.recipient_user_id == notification_context["user"].id)) is not None
    session.close()


def test_phase13_retrying_same_payment_event_does_not_duplicate_notifications(phase13_context: dict[str, object]) -> None:
    endpoint = f"/api/v1/agreements/{phase13_context['agreement'].id}/payments/advance"
    first = phase13_context["client"].post(endpoint, headers=auth(phase13_context["consumer"]))
    second = phase13_context["client"].post(endpoint, headers=auth(phase13_context["consumer"]))
    assert first.status_code == 200
    assert second.status_code == 200
    session = phase13_context["factory"]()
    assert len(session.scalars(select(Notification.id).where(Notification.notification_type == NotificationType.ADVANCE_PAYMENT_COMPLETED)).all()) == 2
    session.close()


def test_phase13_request_cannot_redirect_notification_and_unrelated_user_cannot_read_it(phase13_context: dict[str, object]) -> None:
    item = application(phase13_context)
    response = phase13_context["client"].post(
        f"/api/v1/applications/{item['id']}/counter-offer",
        headers=auth(phase13_context["worker"]),
        json={"proposed_amount": "1100", "recipient_user_id": str(phase13_context["unrelated"].id), "recipient_email": phase13_context["unrelated"].email},
    )
    assert response.status_code == 200
    assert_phase13_recipients(phase13_context, NotificationType.COUNTER_OFFER_RECEIVED, phase13_context["consumer"])
    assert phase13_context["client"].get("/api/v1/notifications", headers=auth(phase13_context["unrelated"])).json()["total"] == 0


def test_phase13_sender_comes_from_server_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "server@example.com")
    monkeypatch.setenv("SMTP_FROM_NAME", "Server Name")
    get_settings.cache_clear()
    captured: list[object] = []

    class CaptureSMTP:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            assert host == "smtp.example.com"

        def __enter__(self) -> "CaptureSMTP":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def starttls(self) -> None:
            return None

        def send_message(self, message: object) -> None:
            captured.append(message)

    monkeypatch.setattr("app.providers.email.smtplib.SMTP", CaptureSMTP)
    assert SMTPEmailProvider().send(EmailMessageData("recipient@example.com", "Subject", "Body")) is True
    assert captured[0]["From"] == "Server Name <server@example.com>"
    assert captured[0]["To"] == "recipient@example.com"