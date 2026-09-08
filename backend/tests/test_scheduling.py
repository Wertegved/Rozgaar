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
from app.db.base import Base
from app.db.models.agreements import Agreement
from app.db.models.enums import AccountStatus, AgreementStatus, EmergencyLevel, JobStatus, UserRole
from app.db.models.jobs import Job
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def schedule_context(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, object], None, None]:
    monkeypatch.setenv("JWT_SECRET_KEY", "phase-eight-test-secret-key-32-bytes-long")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    consumer = User(name="Consumer", phone="9300000001", email="consumer8@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    worker = User(name="Worker", phone="9300000002", email="worker8@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    other_worker = User(name="Other Worker", phone="9300000003", email="worker82@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    other_consumer = User(name="Other Consumer", phone="9300000004", email="consumer82@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    session.add_all([consumer, worker, other_worker, other_consumer])
    session.flush()
    consumer_profile = ConsumerProfile(user_id=consumer.id)
    other_profile = ConsumerProfile(user_id=other_consumer.id)
    worker_profile = WorkerProfile(user_id=worker.id)
    other_worker_profile = WorkerProfile(user_id=other_worker.id)
    scheduled = date.today() + timedelta(days=3)
    job = Job(consumer=consumer_profile, category="painting", title="Scheduled job", description="Paint", location="Mumbai", required_worker_count=1, minimum_platform_cost=Decimal("1000"), emergency_level=EmergencyLevel.RELAXED, scheduled_date=scheduled, start_time=time(10), end_time=time(12), status=JobStatus.POSTED)
    other_job = Job(consumer=other_profile, category="cleaning", title="Other job", description="Clean", location="Mumbai", required_worker_count=1, minimum_platform_cost=Decimal("500"), emergency_level=EmergencyLevel.RELAXED, scheduled_date=scheduled, start_time=time(11), end_time=time(13), status=JobStatus.POSTED)
    session.add_all([consumer_profile, other_profile, worker_profile, other_worker_profile, job, other_job])
    session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        request_session = factory()
        try:
            yield request_session
        finally:
            request_session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield {"client": client, "factory": factory, "consumer": consumer, "worker": worker, "other_worker": other_worker, "other_consumer": other_consumer, "job": job, "other_job": other_job, "scheduled": scheduled}
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def apply(client: TestClient, job: Job, worker: User) -> dict[str, object]:
    return client.post(f"/api/v1/jobs/{job.id}/applications", headers=auth(worker), json={"proposed_price": "1200"}).json()


def test_worker_availability_crud_and_ownership(schedule_context: dict[str, object]) -> None:
    client = schedule_context["client"]
    worker = schedule_context["worker"]
    other_worker = schedule_context["other_worker"]
    window = client.post("/api/v1/workers/me/availability", headers=auth(worker), json={"available_date": str(schedule_context["scheduled"]), "start_time": "09:00", "end_time": "18:00"})
    assert window.status_code == 201
    assert len(client.get("/api/v1/workers/me/availability", headers=auth(worker)).json()) == 1
    assert client.patch(f"/api/v1/workers/me/availability/{window.json()['id']}", headers=auth(other_worker), json={"available_date": str(schedule_context["scheduled"]), "start_time": "10:00", "end_time": "11:00"}).status_code == 403
    assert client.delete(f"/api/v1/workers/me/availability/{window.json()['id']}", headers=auth(worker)).status_code == 204


def test_availability_rejects_invalid_and_overlapping_windows(schedule_context: dict[str, object]) -> None:
    client = schedule_context["client"]
    worker = schedule_context["worker"]
    payload = {"available_date": str(schedule_context["scheduled"]), "start_time": "14:00", "end_time": "10:00"}
    assert client.post("/api/v1/workers/me/availability", headers=auth(worker), json=payload).status_code == 422
    first = client.post("/api/v1/workers/me/availability", headers=auth(worker), json={**payload, "start_time": "09:00", "end_time": "12:00"})
    assert first.status_code == 201
    boundary = client.post("/api/v1/workers/me/availability", headers=auth(worker), json={**payload, "start_time": "12:00", "end_time": "14:00"})
    assert boundary.status_code == 201
    assert client.post("/api/v1/workers/me/availability", headers=auth(worker), json={**payload, "start_time": "11:00", "end_time": "13:00"}).status_code == 409


def test_hiring_requires_availability_and_rolls_back(schedule_context: dict[str, object]) -> None:
    client = schedule_context["client"]
    worker = schedule_context["worker"]
    consumer = schedule_context["consumer"]
    job = schedule_context["job"]
    application = apply(client, job, worker)
    rejected = client.post(f"/api/v1/applications/{application['id']}/accept", headers=auth(consumer))
    assert rejected.status_code == 200  # no explicit windows means no restriction

    availability = client.post(
        "/api/v1/workers/me/availability",
        headers=auth(worker),
        json={
            "available_date": str(schedule_context["scheduled"]),
            "start_time": "08:00",
            "end_time": "10:00",
        },
    )
    assert availability.status_code == 201
    second_application = apply(client, schedule_context["other_job"], worker)
    unavailable = client.post(f"/api/v1/applications/{second_application['id']}/accept", headers=auth(schedule_context["other_consumer"]))
    assert unavailable.status_code == 409  # overlap with the first active agreement

    session = schedule_context["factory"]()
    assert session.scalar(select(Agreement).where(Agreement.job_id == schedule_context["other_job"].id)) is None
    session.close()


def test_exact_boundary_is_allowed_and_schedule_is_private(schedule_context: dict[str, object]) -> None:
    client = schedule_context["client"]
    worker = schedule_context["worker"]
    consumer = schedule_context["consumer"]
    other_consumer = schedule_context["other_consumer"]
    job = schedule_context["job"]
    first = apply(client, job, worker)
    assert client.post(f"/api/v1/applications/{first['id']}/accept", headers=auth(consumer)).status_code == 200
    schedule = client.get("/api/v1/workers/me/schedule", headers=auth(worker))
    assert schedule.status_code == 200
    assert schedule.json()[0]["job_id"] == str(job.id)
    assert client.get(f"/api/v1/jobs/{job.id}/schedule", headers=auth(consumer)).status_code == 200
    assert client.get(f"/api/v1/jobs/{job.id}/schedule", headers=auth(other_consumer)).status_code == 404
    assert client.get("/api/v1/workers/me/schedule", headers=auth(other_consumer)).status_code == 403