from collections.abc import Generator
from datetime import date, time
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
from app.db.models.enums import AccountStatus, AgreementStatus, ComplaintStatus, EmergencyLevel, JobStatus, UserRole
from app.db.models.jobs import Job
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def issue_context(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, object], None, None]:
    monkeypatch.setenv("JWT_SECRET_KEY", "phase-twelve-test-secret-key-32-bytes-long")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    consumer = User(name="Consumer", phone="9700000001", email="consumer12@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    worker = User(name="Worker", phone="9700000002", email="worker12@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    unrelated = User(name="Unrelated", phone="9700000003", email="unrelated12@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    admin = User(name="Admin", phone="9700000004", email="admin12@example.com", password_hash=hash_password("password123"), role=UserRole.ADMIN, account_status=AccountStatus.ACTIVE)
    session.add_all([consumer, worker, unrelated, admin])
    session.flush()
    consumer_profile = ConsumerProfile(user_id=consumer.id)
    worker_profile = WorkerProfile(user_id=worker.id)
    job = Job(consumer=consumer_profile, category="painting", title="Issue job", description="Paint", location="Mumbai", required_worker_count=1, minimum_platform_cost=Decimal("1000"), emergency_level=EmergencyLevel.RELAXED, status=JobStatus.COMPLETED)
    agreement = Agreement(job=job, worker=worker_profile, agreed_price=Decimal("1000"), agreed_date=date.today(), start_time=time(10), end_time=time(12), worker_count=1, status=AgreementStatus.ACTIVE)
    session.add_all([consumer_profile, worker_profile, job, agreement])
    session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        request_session = factory()
        try:
            yield request_session
        finally:
            request_session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield {"client": client, "factory": factory, "consumer": consumer, "worker": worker, "unrelated": unrelated, "admin": admin, "job": job}
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def test_complaint_creation_visibility_and_admin_response(issue_context: dict[str, object]) -> None:
    client = issue_context["client"]
    consumer = issue_context["consumer"]
    unrelated = issue_context["unrelated"]
    admin = issue_context["admin"]
    job = issue_context["job"]
    created = client.post("/api/v1/complaints", headers=auth(consumer), json={"job_id": str(job.id), "category": "PAYMENT", "message": "Payment issue"})
    assert created.status_code == 201
    complaint_id = created.json()["id"]
    assert client.get("/api/v1/complaints/my", headers=auth(consumer)).json()["total"] == 1
    assert client.get(f"/api/v1/complaints/{complaint_id}", headers=auth(unrelated)).status_code == 403
    assert client.get(f"/api/v1/admin/complaints/{complaint_id}", headers=auth(admin)).status_code == 200
    response = client.post(f"/api/v1/admin/complaints/{complaint_id}/response", headers=auth(admin), json={"response": "Under review by the cooperative."})
    assert response.status_code == 200
    assert response.json()["status"] == "RESPONDED"
    assert client.patch(f"/api/v1/admin/complaints/{complaint_id}/status", headers=auth(admin), json={"status": "RESOLVED"}).status_code == 200


def test_unrelated_job_complaint_and_dispute_are_rejected(issue_context: dict[str, object]) -> None:
    client = issue_context["client"]
    unrelated = issue_context["unrelated"]
    worker = issue_context["worker"]
    job = issue_context["job"]
    assert client.post("/api/v1/complaints", headers=auth(unrelated), json={"job_id": str(job.id), "category": "GENERAL", "message": "Not my job"}).status_code == 403
    assert client.post(f"/api/v1/jobs/{job.id}/disputes", headers=auth(unrelated), json={"category": "PAYMENT", "description": "Not involved"}).status_code == 403
    dispute = client.post(f"/api/v1/jobs/{job.id}/disputes", headers=auth(worker), json={"category": "JOB_ISSUE", "description": "Work issue"})
    assert dispute.status_code == 201


def test_admin_dispute_context_and_resolution_preserve_other_state(issue_context: dict[str, object]) -> None:
    client = issue_context["client"]
    consumer = issue_context["consumer"]
    admin = issue_context["admin"]
    job = issue_context["job"]
    created = client.post(f"/api/v1/jobs/{job.id}/disputes", headers=auth(consumer), json={"category": "COMPLETION_DISAGREEMENT", "description": "Please investigate."})
    dispute_id = created.json()["id"]
    detail = client.get(f"/api/v1/admin/disputes/{dispute_id}", headers=auth(admin))
    assert detail.status_code == 200
    assert detail.json()["job_title"] == "Issue job"
    assert detail.json()["job_status"] == "COMPLETED"
    resolved = client.post(f"/api/v1/admin/disputes/{dispute_id}/resolve", headers=auth(admin), json={"resolution": "Reviewed neutrally."})
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"
    session = issue_context["factory"]()
    assert session.get(Job, job.id).status is JobStatus.COMPLETED
    session.close()