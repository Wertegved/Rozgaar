from collections.abc import Generator
from datetime import date, time
from decimal import Decimal
from uuid import uuid4
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
from app.db.models.enums import AccountStatus, EmergencyLevel, UserRole
from app.db.models.skills import Skill
from app.db.models.users import ConsumerProfile, User, WorkerProfile, WorkerSkill
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def job_context(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, object], None, None]:
    monkeypatch.setenv("JWT_SECRET_KEY", "phase-six-test-secret-key-32-bytes-long")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    session = session_factory()
    consumer = User(
        name="Consumer", phone="9100000001", email="consumer@example.com",
        password_hash=hash_password("password123"), role=UserRole.CONSUMER,
        account_status=AccountStatus.ACTIVE,
    )
    worker = User(
        name="Worker", phone="9100000002", email="worker@example.com",
        password_hash=hash_password("password123"), role=UserRole.WORKER,
        account_status=AccountStatus.ACTIVE,
    )
    admin = User(
        name="Admin", phone="9100000003", email="admin@example.com",
        password_hash=hash_password("password123"), role=UserRole.ADMIN,
        account_status=AccountStatus.ACTIVE,
    )
    session.add_all([consumer, worker, admin])
    session.flush()
    consumer_profile = ConsumerProfile(user_id=consumer.id)
    worker_profile = WorkerProfile(user_id=worker.id)
    skill = Skill(name="Painting")
    session.add_all([consumer_profile, worker_profile, skill])
    session.commit()
    skill = session.scalar(select(Skill).where(Skill.name == "Painting"))
    session.add(WorkerSkill(worker_id=worker_profile.id, skill_id=skill.id))
    session.commit()
    session.close()

    def override_get_db() -> Generator[Session, None, None]:
        request_session = session_factory()
        try:
            yield request_session
        finally:
            request_session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield {
            "client": client,
            "session_factory": session_factory,
            "consumer": consumer,
            "worker": worker,
            "admin": admin,
            "skill": skill,
        }
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def token(user: User) -> str:
    return create_access_token(user.id, user.role)


def headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(user)}"}


def create_payload(skill_id: str | None = None) -> dict[str, object]:
    return {
        "category": "painting",
        "title": "Paint the living room",
        "description": "Interior painting for one room.",
        "location": "Mumbai Central",
        "required_worker_count": 2,
        "minimum_platform_cost": "1500.00",
        "emergency_level": "RELAXED",
        "scheduled_date": str(date.today()),
        "start_time": "09:00:00",
        "end_time": "12:00:00",
        "required_skill_ids": [skill_id] if skill_id else [],
        "images": [{"storage_bucket": "job-images", "storage_path": "jobs/example.jpg"}],
    }


def test_consumer_can_create_job_and_owner_is_server_derived(job_context: dict[str, object]) -> None:
    client = job_context["client"]
    consumer = job_context["consumer"]
    skill = job_context["skill"]
    response = client.post("/api/v1/jobs", headers=headers(consumer), json=create_payload(str(skill.id)))

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "POSTED"
    assert body["required_skills"][0]["name"] == "Painting"
    assert body["images"][0]["storage_path"] == "jobs/example.jpg"

    session = job_context["session_factory"]()
    from app.db.models.jobs import Job
    job = session.scalar(select(Job).where(Job.id == UUID(body["id"])))
    profile = session.scalar(select(ConsumerProfile).where(ConsumerProfile.user_id == consumer.id))
    assert job.consumer_id == profile.id
    session.close()


def test_worker_and_admin_cannot_create_jobs(job_context: dict[str, object]) -> None:
    client = job_context["client"]
    assert client.post("/api/v1/jobs", headers=headers(job_context["worker"]), json=create_payload()).status_code == 403
    assert client.post("/api/v1/jobs", headers=headers(job_context["admin"]), json=create_payload()).status_code == 403


def test_job_validation_and_invalid_skill_are_rejected(job_context: dict[str, object]) -> None:
    client = job_context["client"]
    consumer = job_context["consumer"]
    invalid = create_payload()
    invalid.update({"required_worker_count": 0, "minimum_platform_cost": "-1", "start_time": "12:00:00", "end_time": "09:00:00"})
    assert client.post("/api/v1/jobs", headers=headers(consumer), json=invalid).status_code == 422
    missing_skill = create_payload(str(uuid4()))
    assert client.post("/api/v1/jobs", headers=headers(consumer), json=missing_skill).status_code == 422


def test_worker_discovery_filters_and_pagination(job_context: dict[str, object]) -> None:
    client = job_context["client"]
    consumer = job_context["consumer"]
    worker = job_context["worker"]
    for index in range(3):
        payload = create_payload()
        payload["title"] = f"Paint room {index}"
        payload["minimum_platform_cost"] = str(1000 + index * 500)
        assert client.post("/api/v1/jobs", headers=headers(consumer), json=payload).status_code == 201

    response = client.get("/api/v1/jobs?min_price=1500&page=1&page_size=1", headers=headers(worker))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page_size"] == 1
    assert len(body["items"]) == 1


def test_worker_discovery_respects_saved_working_region(job_context: dict[str, object]) -> None:
    client = job_context["client"]
    consumer = job_context["consumer"]
    worker = job_context["worker"]
    session = job_context["session_factory"]()
    worker_profile = session.scalar(select(WorkerProfile).where(WorkerProfile.user_id == worker.id))
    worker_profile.working_location = "Salt Lake, Kolkata"
    worker_profile.working_latitude = 22.5726
    worker_profile.working_longitude = 88.3639
    session.commit()
    session.close()

    local_job = create_payload()
    local_job.update({
        "location": "Salt Lake, Kolkata",
        "title": "Local painting job",
        "category": "painting",
        "minimum_platform_cost": "1500.00",
    })
    distant_job = create_payload()
    distant_job.update({
        "location": "Mumbai Central",
        "title": "Mumbai painting job",
        "category": "painting",
        "minimum_platform_cost": "2000.00",
    })

    assert client.post("/api/v1/jobs", headers=headers(consumer), json=local_job).status_code == 201
    assert client.post("/api/v1/jobs", headers=headers(consumer), json=distant_job).status_code == 201

    response = client.get("/api/v1/jobs?page=1&page_size=20", headers=headers(worker))
    assert response.status_code == 200
    titles = {item["title"] for item in response.json()["items"]}
    assert "Local painting job" in titles
    assert "Mumbai painting job" not in titles


def test_consumer_location_intelligence_includes_matching_workers(job_context: dict[str, object]) -> None:
    client = job_context["client"]
    consumer = job_context["consumer"]
    worker = job_context["worker"]
    session = job_context["session_factory"]()
    profile = session.scalar(select(WorkerProfile).where(WorkerProfile.user_id == worker.id))
    profile.working_location = "Salt Lake, Kolkata"
    profile.working_latitude = 22.5726
    profile.working_longitude = 88.3639
    profile.availability = "AVAILABLE"
    session.commit()
    session.close()

    response = client.get("/api/v1/location-intelligence/consumer?location=Salt%20Lake%2C%20Kolkata&category=painting", headers=headers(consumer))
    assert response.status_code == 200
    body = response.json()
    assert body["nearby_worker_count"] >= 1
    assert body["nearby_workers"][0]["name"] == "Worker"
    assert body["nearby_workers"][0]["availability"] == "AVAILABLE"


def test_job_detail_and_access_controls(job_context: dict[str, object]) -> None:
    client = job_context["client"]
    consumer = job_context["consumer"]
    worker = job_context["worker"]
    created = client.post("/api/v1/jobs", headers=headers(consumer), json=create_payload()).json()
    detail = client.get(f"/api/v1/jobs/{created['id']}", headers=headers(worker))

    assert detail.status_code == 200
    assert "password_hash" not in detail.text
    assert client.get(f"/api/v1/jobs/{uuid4()}", headers=headers(worker)).status_code == 404
    assert client.get("/api/v1/jobs", headers=headers(consumer)).json()["total"] == 1


def test_only_owner_can_modify_job_and_status_is_server_controlled(job_context: dict[str, object]) -> None:
    client = job_context["client"]
    consumer = job_context["consumer"]
    worker = job_context["worker"]
    created = client.post("/api/v1/jobs", headers=headers(consumer), json=create_payload()).json()

    updated = client.patch(
        f"/api/v1/jobs/{created['id']}",
        headers=headers(consumer),
        json={"title": "Updated title", "status": "COMPLETED"},
    )
    worker_update = client.patch(
        f"/api/v1/jobs/{created['id']}", headers=headers(worker), json={"title": "Not allowed"}
    )

    assert updated.status_code == 422
    assert worker_update.status_code == 403


def test_job_routes_are_documented(job_context: dict[str, object]) -> None:
    document = job_context["client"].get("/openapi.json").json()

    assert "/api/v1/jobs" in document["paths"]
    assert "/api/v1/jobs/{job_id}" in document["paths"]