from collections.abc import Generator
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.hashing import hash_password
from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.core.errors import APIError
from app.db.base import Base
from app.db.models.agreements import Agreement
from app.db.models.enums import AccountStatus, AgreementStatus, EmergencyLevel, JobStatus, PaymentStatus, PaymentType, UserRole
from app.db.models.jobs import Job
from app.db.models.payments import Payment
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.db.session import get_db
from app.main import app
from app.providers.simulated import SimulatedPaymentProvider
from app.services.payment_service import pay_advance


@pytest.fixture()
def payment_context(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, object], None, None]:
    monkeypatch.setenv("JWT_SECRET_KEY", "phase-nine-test-secret-key-32-bytes-long")
    monkeypatch.setenv("PAYMENT_ADVANCE_PERCENTAGE", "20")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    consumer = User(name="Consumer", phone="9400000001", email="consumer9@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    worker = User(name="Worker", phone="9400000002", email="worker9@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    other_consumer = User(name="Other", phone="9400000003", email="other9@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    admin = User(name="Admin", phone="9400000004", email="admin9@example.com", password_hash=hash_password("password123"), role=UserRole.ADMIN, account_status=AccountStatus.ACTIVE)
    session.add_all([consumer, worker, other_consumer, admin])
    session.flush()
    consumer_profile = ConsumerProfile(user_id=consumer.id)
    other_profile = ConsumerProfile(user_id=other_consumer.id)
    worker_profile = WorkerProfile(user_id=worker.id)
    scheduled = date.today() + timedelta(days=2)
    job = Job(consumer=consumer_profile, category="painting", title="Paid job", description="Paint", location="Mumbai", required_worker_count=1, minimum_platform_cost=Decimal("1000"), emergency_level=EmergencyLevel.RELAXED, scheduled_date=scheduled, start_time=time(10), end_time=time(12), status=JobStatus.ACCEPTED)
    agreement = Agreement(job=job, worker=worker_profile, agreed_price=Decimal("1000.00"), agreed_date=scheduled, start_time=time(10), end_time=time(12), worker_count=1, status=AgreementStatus.ACTIVE)
    session.add_all([consumer_profile, other_profile, worker_profile, job, agreement])
    session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        request_session = factory()
        try:
            yield request_session
        finally:
            request_session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield {"client": client, "factory": factory, "consumer": consumer, "worker": worker, "other_consumer": other_consumer, "admin": admin, "agreement": agreement}
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def test_simulated_provider_success_and_failure() -> None:
    success = SimulatedPaymentProvider().create_payment(Decimal("10.00"), {})
    failure = SimulatedPaymentProvider(should_fail=True).create_payment(Decimal("10.00"), {})

    assert success.success is True
    assert success.reference.startswith("SIM-")
    assert failure.success is False


def test_consumer_can_pay_derived_advance_and_final_remains_pending(payment_context: dict[str, object]) -> None:
    client = payment_context["client"]
    consumer = payment_context["consumer"]
    agreement = payment_context["agreement"]
    response = client.post(f"/api/v1/agreements/{agreement.id}/payments/advance", headers=auth(consumer))

    assert response.status_code == 200
    body = response.json()
    assert body["payment_type"] == "ADVANCE"
    assert body["status"] == "COMPLETED"
    assert body["advance_amount"] == "200.00"
    assert body["final_amount"] == "800.00"
    assert body["transaction_reference"].startswith("SIM-")

    payments = client.get(f"/api/v1/agreements/{agreement.id}/payments", headers=auth(consumer))
    assert payments.status_code == 200
    assert len(payments.json()["items"]) == 2
    assert payments.json()["items"][1]["payment_type"] == "FINAL"
    assert payments.json()["items"][1]["status"] == "PENDING"


def test_advance_is_idempotent_and_worker_can_view_history(payment_context: dict[str, object]) -> None:
    client = payment_context["client"]
    consumer = payment_context["consumer"]
    worker = payment_context["worker"]
    agreement = payment_context["agreement"]
    first = client.post(f"/api/v1/agreements/{agreement.id}/payments/advance", headers=auth(consumer)).json()
    second = client.post(f"/api/v1/agreements/{agreement.id}/payments/advance", headers=auth(consumer)).json()
    history = client.get("/api/v1/workers/me/payments", headers=auth(worker))

    assert first["id"] == second["id"]
    assert first["transaction_reference"] == second["transaction_reference"]
    assert len(history.json()["items"]) == 2
    assert history.json()["simulated_transaction_value"] == "200.00"


def test_payment_authorization_and_admin_read_only_visibility(payment_context: dict[str, object]) -> None:
    client = payment_context["client"]
    consumer = payment_context["consumer"]
    worker = payment_context["worker"]
    other_consumer = payment_context["other_consumer"]
    admin = payment_context["admin"]
    agreement = payment_context["agreement"]
    payment = client.post(f"/api/v1/agreements/{agreement.id}/payments/advance", headers=auth(consumer)).json()

    assert client.post(f"/api/v1/agreements/{agreement.id}/payments/advance", headers=auth(worker)).status_code == 403
    assert client.post(f"/api/v1/agreements/{agreement.id}/payments/advance", headers=auth(other_consumer)).status_code == 403
    assert client.get(f"/api/v1/payments/{payment['id']}", headers=auth(other_consumer)).status_code == 403
    assert client.get("/api/v1/admin/payments", headers=auth(admin)).status_code == 200


def test_failed_provider_is_retryable_without_completed_record(payment_context: dict[str, object]) -> None:
    session = payment_context["factory"]()
    agreement = session.get(Agreement, payment_context["agreement"].id)
    consumer = session.get(User, payment_context["consumer"].id)
    with pytest.raises(APIError):
        pay_advance(session, consumer, agreement.id, SimulatedPaymentProvider(should_fail=True))
    assert session.scalar(select(Payment).where(Payment.agreement_id == agreement.id, Payment.payment_type == PaymentType.ADVANCE)).status is PaymentStatus.FAILED
    session.close()


def test_inactive_agreement_rejected(payment_context: dict[str, object]) -> None:
    session = payment_context["factory"]()
    agreement = session.get(Agreement, payment_context["agreement"].id)
    agreement.status = AgreementStatus.CANCELLED
    session.commit()
    session.close()
    response = payment_context["client"].post(f"/api/v1/agreements/{agreement.id}/payments/advance", headers=auth(payment_context["consumer"]))

    assert response.status_code == 409