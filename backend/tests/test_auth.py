from collections.abc import Generator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import require_admin, require_consumer, require_worker
from app.core.config import get_settings
from app.db.base import Base
from app.db.models.enums import AccountStatus, UserRole
from app.db.models.users import User
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("JWT_SECRET_KEY", "phase-five-test-secret-key-32-bytes-long")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.auth_session_factory = session_factory
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def register(client: TestClient, role: str = "CONSUMER", email: str = "person@example.com"):
    return client.post(
        "/api/v1/auth/register",
        json={
            "name": "Test Person",
            "phone": "9000000001" if role == "CONSUMER" else "9000000002",
            "email": email,
            "password": "correct horse battery",
            "role": role,
        },
    )


def test_consumer_and_worker_registration_are_safe(client: TestClient) -> None:
    consumer = register(client)
    worker = register(client, role="WORKER", email="worker@example.com")

    assert consumer.status_code == 201
    assert worker.status_code == 201
    assert "password_hash" not in consumer.json()
    assert "password" not in consumer.json()
    with client.auth_session_factory() as session:
        user = session.scalar(select(User).where(User.email == "person@example.com"))
        assert user is not None
        assert user.password_hash != "correct horse battery"
        assert user.password_hash.startswith("$argon2")


def test_admin_registration_is_rejected(client: TestClient) -> None:
    response = register(client, role="ADMIN", email="admin@example.com")

    assert response.status_code == 403


def test_duplicate_email_and_invalid_input_are_rejected(client: TestClient) -> None:
    assert register(client).status_code == 201
    duplicate = register(client, email="PERSON@example.com")
    invalid = client.post(
        "/api/v1/auth/register",
        json={"name": "X", "phone": "1", "email": "bad", "password": "short", "role": "CONSUMER"},
    )

    assert duplicate.status_code == 409
    assert invalid.status_code == 422


def test_login_returns_bearer_token_and_current_user(client: TestClient) -> None:
    register(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "PERSON@example.com", "password": "correct horse battery"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "CONSUMER"
    assert "password_hash" not in body["user"]

    current = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert current.status_code == 200
    assert current.json()["email"] == "person@example.com"


def test_invalid_missing_malformed_and_expired_tokens_are_rejected(client: TestClient) -> None:
    register(client)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Basic token"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer malformed"}).status_code == 401

    from datetime import datetime, timedelta, timezone
    import jwt

    expired = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000", "type": "access", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        "phase-five-test-secret-key-32-bytes-long",
        algorithm="HS256",
    )
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_invalid_credentials_and_inactive_account_are_rejected(client: TestClient) -> None:
    register(client)
    bad_password = client.post(
        "/api/v1/auth/login",
        json={"email": "person@example.com", "password": "wrong password"},
    )
    missing = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong password"},
    )

    assert bad_password.status_code == 401
    assert missing.status_code == 401

    with client.auth_session_factory() as session:
        user = session.scalar(select(User).where(User.email == "person@example.com"))
        assert user is not None
        user.account_status = AccountStatus.SUSPENDED
        session.commit()

    inactive = client.post(
        "/api/v1/auth/login",
        json={"email": "person@example.com", "password": "correct horse battery"},
    )
    assert inactive.status_code == 401


def test_role_dependencies_enforce_backend_roles() -> None:
    consumer = User(role=UserRole.CONSUMER, name="C", phone="1")
    worker = User(role=UserRole.WORKER, name="W", phone="2")
    admin = User(role=UserRole.ADMIN, name="A", phone="3")

    assert require_consumer(consumer) is consumer
    assert require_worker(worker) is worker
    assert require_admin(admin) is admin
    with pytest.raises(HTTPException) as consumer_error:
        require_consumer(worker)
    with pytest.raises(HTTPException) as worker_error:
        require_worker(consumer)
    with pytest.raises(HTTPException) as admin_error:
        require_admin(consumer)
    assert consumer_error.value.status_code == 403
    assert worker_error.value.status_code == 403
    assert admin_error.value.status_code == 403


def test_auth_routes_and_bearer_scheme_are_documented(client: TestClient) -> None:
    openapi = client.get("/openapi.json")
    document = openapi.json()

    assert openapi.status_code == 200
    assert "/api/v1/auth/register" in document["paths"]
    assert "/api/v1/auth/login" in document["paths"]
    assert document["components"]["securitySchemes"]["OAuth2PasswordBearer"]["type"] == "oauth2"