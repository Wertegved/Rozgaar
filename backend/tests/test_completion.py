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
from app.db.models.completion import CompletionEvidence
from app.db.models.enums import AccountStatus, AgreementStatus, EmergencyLevel, EvidenceType, JobStatus, PaymentStatus, PaymentType, UserRole
from app.db.models.jobs import Job
from app.db.models.payments import Payment
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.db.session import get_db
from app.main import app
from app.providers.simulated import SimulatedPaymentProvider
from app.services.completion_service import submit_completion


@pytest.fixture()
def completion_context(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, object], None, None]:
    monkeypatch.setenv("JWT_SECRET_KEY", "phase-ten-test-secret-key-32-bytes-long")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    consumer = User(name="Consumer", phone="9500000001", email="consumer10@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    worker = User(name="Worker", phone="9500000002", email="worker10@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    other_consumer = User(name="Other", phone="9500000003", email="other10@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    session.add_all([consumer, worker, other_consumer])
    session.flush()
    consumer_profile = ConsumerProfile(user_id=consumer.id)
    other_profile = ConsumerProfile(user_id=other_consumer.id)
    worker_profile = WorkerProfile(user_id=worker.id)
    scheduled = date.today() + timedelta(days=2)
    job = Job(consumer=consumer_profile, category="painting", title="Completion job", description="Paint", location="Mumbai", required_worker_count=1, minimum_platform_cost=Decimal("1000"), emergency_level=EmergencyLevel.RELAXED, scheduled_date=scheduled, start_time=time(10), end_time=time(12), status=JobStatus.ACCEPTED)
    agreement = Agreement(job=job, worker=worker_profile, agreed_price=Decimal("1000"), agreed_date=scheduled, start_time=time(10), end_time=time(12), worker_count=1, status=AgreementStatus.ACTIVE)
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
        yield {"client": client, "factory": factory, "consumer": consumer, "worker": worker, "other_consumer": other_consumer, "job": job, "agreement": agreement}
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def evidence(path: str) -> dict[str, str]:
    return {"storage_bucket": "completion-evidence", "storage_path": path}


def test_four_conditions_release_final_payment_and_complete_job(completion_context: dict[str, object]) -> None:
    client = completion_context["client"]
    consumer = completion_context["consumer"]
    worker = completion_context["worker"]
    agreement = completion_context["agreement"]
    job = completion_context["job"]
    assert client.post(f"/api/v1/agreements/{agreement.id}/payments/advance", headers=auth(consumer)).status_code == 200
    worker_result = client.post(f"/api/v1/jobs/{job.id}/completion/worker", headers=auth(worker), json=evidence("worker/done.jpg"))
    assert worker_result.status_code == 200
    assert worker_result.json()["job_completed"] is False
    consumer_result = client.post(f"/api/v1/jobs/{job.id}/completion/consumer", headers=auth(consumer), json=evidence("consumer/done.jpg"))
    assert consumer_result.status_code == 200
    assert consumer_result.json()["worker_evidence"] is True
    assert consumer_result.json()["consumer_evidence"] is True
    assert consumer_result.json()["final_payment_completed"] is True
    session = completion_context["factory"]()
    assert session.get(Job, job.id).status is JobStatus.COMPLETED
    final = session.scalar(select(Payment).where(Payment.agreement_id == agreement.id, Payment.payment_type == PaymentType.FINAL))
    assert final.status is PaymentStatus.COMPLETED
    assert final.final_amount == Decimal("800.00")
    session.close()


def test_single_milestone_does_not_complete_and_roles_are_enforced(completion_context: dict[str, object]) -> None:
    client = completion_context["client"]
    consumer = completion_context["consumer"]
    worker = completion_context["worker"]
    other_consumer = completion_context["other_consumer"]
    job = completion_context["job"]
    assert client.post(f"/api/v1/jobs/{job.id}/completion/consumer", headers=auth(worker), json=evidence("wrong.jpg")).status_code == 403
    assert client.post(f"/api/v1/jobs/{job.id}/completion/worker", headers=auth(consumer), json=evidence("wrong.jpg")).status_code == 403
    assert client.post(f"/api/v1/jobs/{job.id}/completion/consumer", headers=auth(other_consumer), json=evidence("wrong.jpg")).status_code == 403
    status = client.get(f"/api/v1/jobs/{job.id}/completion", headers=auth(consumer))
    assert status.status_code == 200
    assert status.json()["job_completed"] is False


def test_invalid_bucket_rejected_and_evidence_metadata_is_private(completion_context: dict[str, object]) -> None:
    client = completion_context["client"]
    worker = completion_context["worker"]
    job = completion_context["job"]
    invalid = client.post(f"/api/v1/jobs/{job.id}/completion/worker", headers=auth(worker), json={"storage_bucket": "job-images", "storage_path": "x.jpg"})
    assert invalid.status_code == 422
    valid = client.post(f"/api/v1/jobs/{job.id}/completion/worker", headers=auth(worker), json=evidence("worker/private.jpg"))
    assert valid.status_code == 200
    session = completion_context["factory"]()
    item = session.scalar(select(CompletionEvidence).where(CompletionEvidence.job_id == job.id))
    assert item.uploaded_by == worker.id
    assert item.evidence_type is EvidenceType.WORKER_COMPLETION
    assert item.storage_bucket == "completion-evidence"
    session.close()


def test_final_payment_failure_preserves_completion_for_retry(completion_context: dict[str, object]) -> None:
    session = completion_context["factory"]()
    consumer = session.get(User, completion_context["consumer"].id)
    worker = session.get(User, completion_context["worker"].id)
    job = session.get(Job, completion_context["job"].id)
    agreement = session.get(Agreement, completion_context["agreement"].id)
    from app.services.payment_service import pay_advance
    pay_advance(session, consumer, agreement.id)
    submit_completion(session, worker, job.id, type("Request", (), {"storage_bucket": "completion-evidence", "storage_path": "worker/fail.jpg"})(), UserRole.WORKER)
    with pytest.raises(Exception):
        submit_completion(session, consumer, job.id, type("Request", (), {"storage_bucket": "completion-evidence", "storage_path": "consumer/fail.jpg"})(), UserRole.CONSUMER, SimulatedPaymentProvider(should_fail=True))
    assert session.get(Job, job.id).status is not JobStatus.COMPLETED
    session.close()