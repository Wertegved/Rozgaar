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
from app.db.models.enums import AccountStatus, AgreementStatus, EmergencyLevel, JobStatus, UserRole
from app.db.models.jobs import Job
from app.db.models.reviews import Review
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def review_context(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, object], None, None]:
    monkeypatch.setenv("JWT_SECRET_KEY", "phase-eleven-test-secret-key-32-bytes-long")
    get_settings.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    consumer = User(name="Consumer", phone="9600000001", email="consumer11@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    worker = User(name="Worker", phone="9600000002", email="worker11@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    worker_two = User(name="Worker Two", phone="9600000003", email="worker112@example.com", password_hash=hash_password("password123"), role=UserRole.WORKER, account_status=AccountStatus.ACTIVE)
    unrelated = User(name="Unrelated", phone="9600000004", email="unrelated11@example.com", password_hash=hash_password("password123"), role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    session.add_all([consumer, worker, worker_two, unrelated])
    session.flush()
    consumer_profile = ConsumerProfile(user_id=consumer.id)
    worker_profile = WorkerProfile(user_id=worker.id)
    worker_two_profile = WorkerProfile(user_id=worker_two.id)
    job = Job(consumer=consumer_profile, category="painting", title="Completed job", description="Paint", location="Mumbai", required_worker_count=2, minimum_platform_cost=Decimal("1000"), emergency_level=EmergencyLevel.RELAXED, scheduled_date=date.today(), start_time=time(10), end_time=time(12), status=JobStatus.COMPLETED)
    agreement_one = Agreement(job=job, worker=worker_profile, agreed_price=Decimal("500"), agreed_date=date.today(), start_time=time(10), end_time=time(12), worker_count=1, status=AgreementStatus.ACTIVE)
    agreement_two = Agreement(job=job, worker=worker_two_profile, agreed_price=Decimal("500"), agreed_date=date.today(), start_time=time(10), end_time=time(12), worker_count=1, status=AgreementStatus.ACTIVE)
    session.add_all([consumer_profile, worker_profile, worker_two_profile, job, agreement_one, agreement_two])
    session.commit()
    incomplete = Job(consumer_id=consumer_profile.id, category="cleaning", title="Open job", description="Not complete", location="Mumbai", required_worker_count=1, minimum_platform_cost=Decimal("100"), emergency_level=EmergencyLevel.RELAXED, status=JobStatus.ACCEPTED)
    session.add(incomplete)
    session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        request_session = factory()
        try:
            yield request_session
        finally:
            request_session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield {"client": client, "factory": factory, "consumer": consumer, "worker": worker, "worker_two": worker_two, "unrelated": unrelated, "job": job, "incomplete": incomplete}
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def review_payload(user_id: str, rating: int = 5) -> dict[str, object]:
    return {"reviewed_user_id": user_id, "rating": rating, "comment": "Excellent work."}


def test_both_sides_can_review_completed_participants(review_context: dict[str, object]) -> None:
    client = review_context["client"]
    consumer = review_context["consumer"]
    worker = review_context["worker"]
    worker_two = review_context["worker_two"]
    worker_two = review_context["worker_two"]
    job = review_context["job"]
    first = client.post(f"/api/v1/jobs/{job.id}/reviews", headers=auth(consumer), json=review_payload(str(worker.id), 5))
    second = client.post(f"/api/v1/jobs/{job.id}/reviews", headers=auth(worker), json=review_payload(str(consumer.id), 4))
    third = client.post(f"/api/v1/jobs/{job.id}/reviews", headers=auth(consumer), json=review_payload(str(worker_two.id), 3))

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 201
    assert len(client.get(f"/api/v1/jobs/{job.id}/reviews", headers=auth(consumer)).json()) == 3


def test_reviews_require_completion_and_valid_pair(review_context: dict[str, object]) -> None:
    client = review_context["client"]
    consumer = review_context["consumer"]
    worker = review_context["worker"]
    unrelated = review_context["unrelated"]
    job = review_context["job"]
    incomplete = review_context["incomplete"]
    assert client.post(f"/api/v1/jobs/{incomplete.id}/reviews", headers=auth(consumer), json=review_payload(str(worker.id))).status_code == 409
    assert client.post(f"/api/v1/jobs/{job.id}/reviews", headers=auth(unrelated), json=review_payload(str(worker.id))).status_code == 403
    assert client.post(f"/api/v1/jobs/{job.id}/reviews", headers=auth(consumer), json=review_payload(str(consumer.id))).status_code == 422


def test_duplicate_rating_and_input_validation(review_context: dict[str, object]) -> None:
    client = review_context["client"]
    consumer = review_context["consumer"]
    worker = review_context["worker"]
    job = review_context["job"]
    payload = review_payload(str(worker.id))
    assert client.post(f"/api/v1/jobs/{job.id}/reviews", headers=auth(consumer), json=payload).status_code == 201
    assert client.post(f"/api/v1/jobs/{job.id}/reviews", headers=auth(consumer), json=payload).status_code == 409
    assert client.post(f"/api/v1/jobs/{job.id}/reviews", headers=auth(consumer), json=review_payload(str(worker.id), 6)).status_code == 422
    assert client.post(f"/api/v1/jobs/{job.id}/reviews", headers=auth(consumer), json={"reviewed_user_id": str(worker.id), "rating": 1, "comment": "x" * 2001}).status_code == 422


def test_reputation_and_my_history_are_derived(review_context: dict[str, object]) -> None:
    client = review_context["client"]
    consumer = review_context["consumer"]
    worker = review_context["worker"]
    worker_two = review_context["worker_two"]
    job = review_context["job"]
    review_pairs = [(consumer, worker, 5), (worker, consumer, 4), (consumer, worker_two, 5)]
    for reviewer, reviewed, rating in review_pairs:
        assert client.post(f"/api/v1/jobs/{job.id}/reviews", headers=auth(reviewer), json=review_payload(str(reviewed.id), rating)).status_code == 201
    reputation = client.get(f"/api/v1/users/{worker.id}/reviews", headers=auth(consumer))
    history = client.get("/api/v1/reviews/my", headers=auth(consumer))

    assert reputation.status_code == 200
    assert reputation.json()["average_rating"] == 5.0
    assert reputation.json()["total_reviews"] == 1
    assert reputation.json()["rating_distribution"]["5"] == 1
    assert history.json()["total"] == 2


def test_review_does_not_change_job_or_payment_state(review_context: dict[str, object]) -> None:
    client = review_context["client"]
    consumer = review_context["consumer"]
    worker = review_context["worker"]
    job = review_context["job"]
    assert client.post(f"/api/v1/jobs/{job.id}/reviews", headers=auth(consumer), json=review_payload(str(worker.id))).status_code == 201
    session = review_context["factory"]()
    assert session.get(Job, job.id).status is JobStatus.COMPLETED
    assert session.scalar(select(Review).where(Review.job_id == job.id)) is not None
    session.close()