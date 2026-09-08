from collections.abc import Generator
from datetime import date, time
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.hashing import hash_password
from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.db.base import Base
from app.db.models.applications import Application
from app.db.models.enums import AccountStatus, EmergencyLevel, JobStatus, UserRole
from app.db.models.jobs import Job
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def phase7_context(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, object], None, None]:
    monkeypatch.setenv("JWT_SECRET_KEY", "phase-seven-test-secret-key-32-bytes-long")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    consumer = User(name="Consumer", phone="9200000001", email="consumer7@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    worker = User(name="Worker", phone="9200000002", email="worker7@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    second_worker = User(name="Worker Two", phone="9200000003", email="worker72@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    other_consumer = User(name="Other", phone="9200000004", email="other7@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    session.add_all([consumer, worker, second_worker, other_consumer])
    session.flush()
    consumer_profile = ConsumerProfile(user_id=consumer.id)
    other_profile = ConsumerProfile(user_id=other_consumer.id)
    worker_profile = WorkerProfile(user_id=worker.id)
    second_profile = WorkerProfile(user_id=second_worker.id)
    job = Job(consumer=consumer_profile, category="painting", title="Paint job", description="Paint the room", location="Mumbai", required_worker_count=2, minimum_platform_cost=Decimal("1000.00"), emergency_level=EmergencyLevel.RELAXED, scheduled_date=date.today(), start_time=time(9), end_time=time(12), status=JobStatus.POSTED)
    other_job = Job(consumer=other_profile, category="cleaning", title="Other job", description="Clean the room", location="Mumbai", required_worker_count=1, minimum_platform_cost=Decimal("500.00"), emergency_level=EmergencyLevel.RELAXED, scheduled_date=date.today(), start_time=time(9), end_time=time(10), status=JobStatus.POSTED)
    session.add_all([consumer_profile, other_profile, worker_profile, second_profile, job, other_job])
    session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        request_session = factory()
        try:
            yield request_session
        finally:
            request_session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield {"client": client, "factory": factory, "consumer": consumer, "worker": worker, "second_worker": second_worker, "other_consumer": other_consumer, "job": job, "other_job": other_job}
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def test_worker_applies_and_consumer_can_view_applicants(phase7_context: dict[str, object]) -> None:
    client = phase7_context["client"]
    worker = phase7_context["worker"]
    consumer = phase7_context["consumer"]
    job = phase7_context["job"]
    response = client.post(f"/api/v1/jobs/{job.id}/applications", headers=auth_headers(worker), json={"proposed_price": "1250.00"})
    assert response.status_code == 201
    assert response.json()["status"] == "SUBMITTED"
    applicants = client.get(f"/api/v1/jobs/{job.id}/applications", headers=auth_headers(consumer))
    assert applicants.status_code == 200
    assert applicants.json()[0]["worker_name"] == "Worker"
    assert applicants.json()[0]["proposed_price"] == "1250.00"


def test_application_roles_duplicate_and_ownership(phase7_context: dict[str, object]) -> None:
    client = phase7_context["client"]
    worker = phase7_context["worker"]
    consumer = phase7_context["consumer"]
    other_consumer = phase7_context["other_consumer"]
    job = phase7_context["job"]
    assert client.post(f"/api/v1/jobs/{job.id}/applications", headers=auth_headers(consumer), json={"proposed_price": "10"}).status_code == 403
    first = client.post(f"/api/v1/jobs/{job.id}/applications", headers=auth_headers(worker), json={"proposed_price": "100"})
    assert first.status_code == 201
    assert client.post(f"/api/v1/jobs/{job.id}/applications", headers=auth_headers(worker), json={"proposed_price": "100"}).status_code == 409
    assert client.get(f"/api/v1/jobs/{job.id}/applications", headers=auth_headers(other_consumer)).status_code == 403


def test_acceptance_creates_locked_agreement_and_capacity_is_enforced(phase7_context: dict[str, object]) -> None:
    client = phase7_context["client"]
    consumer = phase7_context["consumer"]
    worker = phase7_context["worker"]
    second_worker = phase7_context["second_worker"]
    job = phase7_context["job"]
    first = client.post(f"/api/v1/jobs/{job.id}/applications", headers=auth_headers(worker), json={"proposed_price": "1250"}).json()
    accepted = client.post(f"/api/v1/applications/{first['id']}/accept", headers=auth_headers(consumer))
    assert accepted.status_code == 200
    assert accepted.json()["agreed_price"] == "1250.00"
    assert accepted.json()["status"] == "ACTIVE"
    second = client.post(f"/api/v1/jobs/{job.id}/applications", headers=auth_headers(second_worker), json={"proposed_price": "1300"}).json()
    assert client.post(f"/api/v1/applications/{second['id']}/accept", headers=auth_headers(consumer)).status_code == 200
    third_worker = User(name="Third", phone="9200000005", email="worker73@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    session = phase7_context["factory"]()
    session.add(third_worker)
    session.flush()
    profile = WorkerProfile(user_id=third_worker.id)
    session.add(profile)
    session.commit()
    third = client.post(f"/api/v1/jobs/{job.id}/applications", headers=auth_headers(third_worker), json={"proposed_price": "1400"}).json()
    assert client.post(f"/api/v1/applications/{third['id']}/accept", headers=auth_headers(consumer)).status_code == 409
    session.close()


def test_reject_withdraw_and_my_applications(phase7_context: dict[str, object]) -> None:
    client = phase7_context["client"]
    worker = phase7_context["worker"]
    consumer = phase7_context["consumer"]
    job = phase7_context["job"]
    application = client.post(f"/api/v1/jobs/{job.id}/applications", headers=auth_headers(worker), json={"proposed_price": "100"}).json()
    assert client.get("/api/v1/applications/my", headers=auth_headers(worker)).status_code == 200
    assert client.post(f"/api/v1/applications/{application['id']}/withdraw", headers=auth_headers(worker)).status_code == 204
    assert client.post(f"/api/v1/applications/{application['id']}/reject", headers=auth_headers(consumer)).status_code == 409


def test_negotiation_history_and_counter_acceptance(phase7_context: dict[str, object]) -> None:
    client = phase7_context["client"]
    worker = phase7_context["worker"]
    consumer = phase7_context["consumer"]
    job = phase7_context["job"]
    application = client.post(f"/api/v1/jobs/{job.id}/applications", headers=auth_headers(worker), json={"proposed_price": "100"}).json()
    counter = client.post(f"/api/v1/applications/{application['id']}/counter-offer", headers=auth_headers(consumer), json={"proposed_amount": "110", "message": "Counter"})
    assert counter.status_code == 200
    accepted = client.post(f"/api/v1/negotiations/{counter.json()['id']}/accept", headers=auth_headers(worker))
    assert accepted.status_code == 200
    assert accepted.json()["agreed_price"] == "110.00"
    session = phase7_context["factory"]()
    assert session.scalar(select(Application).where(Application.id == UUID(application["id"]))).status.value == "ACCEPTED"
    session.close()