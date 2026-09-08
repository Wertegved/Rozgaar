from pathlib import Path
from datetime import date, time
from decimal import Decimal
from uuid import uuid4

import jwt
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.core.config import Settings, get_settings
from app.db.models.enums import UserRole
from app.db.base import Base
from app.db.models.enums import AccountStatus, EmergencyLevel, JobStatus
from app.db.models.jobs import Job
from app.db.models.users import ConsumerProfile, User
from app.realtime.payloads import public_payload
from app.schemas.completion import CompletionSubmitRequest
from app.schemas.jobs import JobImageMetadataInput, JobUpdateRequest


def test_security_defaults_keep_secret_values_out_of_configuration_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.jwt_secret_key == ""
    assert settings.supabase_service_role_key is None
    assert settings.smtp_password == ""


def test_mass_assignment_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        JobUpdateRequest.model_validate({"title": "safe", "consumer_id": str(uuid4())})


def test_private_storage_paths_reject_traversal_urls_and_absolute_paths() -> None:
    for schema in (JobImageMetadataInput, CompletionSubmitRequest):
        with pytest.raises(ValidationError):
            schema.model_validate({"storage_path": "../private/file.jpg"})
        with pytest.raises(ValidationError):
            schema.model_validate({"storage_path": "https://example.test/file.jpg"})
        with pytest.raises(ValidationError):
            schema.model_validate({"storage_path": "/private/file.jpg"})


def test_realtime_payload_filter_removes_security_sensitive_fields() -> None:
    payload = public_payload(
        {
            "status": "COMPLETED",
            "password_hash": "hidden",
            "phone": "hidden",
            "email": "hidden",
            "service_role_key": "hidden",
            "storage_path": "private/evidence.jpg",
        }
    )

    assert payload == {"status": "COMPLETED"}


def test_jwt_role_claim_is_not_authority_for_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "phase-six-test-secret-key-32-bytes-long")
    get_settings.cache_clear()
    token = jwt.encode(
        {"sub": str(uuid4()), "role": UserRole.ADMIN.value, "type": "access"},
        "phase-six-test-secret-key-32-bytes-long",
        algorithm="HS256",
    )
    settings = Settings(_env_file=None)
    assert decode_access_token(token)["role"] == UserRole.ADMIN.value
    assert settings.jwt_algorithm == "HS256"
    get_settings.cache_clear()


def test_rls_migration_covers_domain_tables_and_fails_closed_storage() -> None:
    migration_path = Path(__file__).parents[1] / "alembic" / "versions" / "e5f6a7b8c9d0_security_rls_hardening.py"
    source = migration_path.read_text(encoding="utf-8")

    for table in ("users", "jobs", "applications", "agreements", "payments", "completion_evidence", "notifications"):
        assert f'"{table}"' in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "phase16_user_id" in source
    assert "CREATE POLICY phase16_storage_select ON storage.objects FOR SELECT TO authenticated USING (false)" in source
    assert "FORCE ROW LEVEL SECURITY" not in source


def test_security_headers_are_defined_without_exposing_credentials() -> None:
    from app.main import app

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "service_role_key" not in app.openapi().__str__().lower()


def test_cross_consumer_job_detail_is_denied() -> None:
    from app.services.job_service import get_job

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    owner = User(name="Owner", phone="9990000011", role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    unrelated = User(name="Other", phone="9990000012", role=UserRole.CONSUMER, account_status=AccountStatus.ACTIVE)
    owner_profile = ConsumerProfile(user=owner)
    session.add_all([owner, unrelated, owner_profile])
    session.flush()
    job = Job(
        consumer=owner_profile,
        category="cleaning",
        title="Private job",
        description="Private details",
        location="Private address",
        required_worker_count=1,
        minimum_platform_cost=Decimal("100"),
        emergency_level=EmergencyLevel.RELAXED,
        scheduled_date=date.today(),
        start_time=time(9),
        end_time=time(10),
        status=JobStatus.ACCEPTED,
    )
    session.add(job)
    session.commit()

    from app.core.errors import APIError

    with pytest.raises(APIError) as error:
        get_job(session, unrelated, job.id)
    assert error.value.status_code == 403
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()