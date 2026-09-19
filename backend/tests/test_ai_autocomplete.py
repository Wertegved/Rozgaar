from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.providers.fake import FakeAIProvider
from app.ai.service import AIService
from app.api.ai import get_ai_service
from app.api import ai as ai_api
from app.core.config import get_settings
from app.db.base import Base
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
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    get_settings.cache_clear()


def register_and_login(client: TestClient) -> str:
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Test Person",
            "phone": "9000000001",
            "email": "person@example.com",
            "password": "correct horse battery",
            "role": "CONSUMER",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "person@example.com", "password": "correct horse battery"},
    )
    return response.json()["access_token"]


def test_job_description_autocomplete_uses_injected_ai_service(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client)
    provider = FakeAIProvider(response=" with easy access to the work area")
    app.dependency_overrides[get_ai_service] = lambda: AIService(primary=provider, fallback=provider)
    monkeypatch.setattr(ai_api, "consume_rate_limit", lambda *args, **kwargs: True)

    response = client.post(
        "/api/v1/ai/job-description-autocomplete",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Paint living room", "category": "HOME", "partial_description": "Please paint"},
    )

    assert response.status_code == 200
    assert response.json() == {"suggestion": "with easy access to the work area"}
    assert provider.requests[0].system_instruction.startswith("You complete local-service")
    assert "Partial description: Please paint" in provider.requests[0].prompt


def test_job_description_autocomplete_degrades_on_provider_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai.errors import AIProviderUnavailableError

    token = register_and_login(client)
    provider = FakeAIProvider(error=AIProviderUnavailableError("provider down"))
    app.dependency_overrides[get_ai_service] = lambda: AIService(primary=provider, fallback=provider)
    monkeypatch.setattr(ai_api, "consume_rate_limit", lambda *args, **kwargs: True)

    response = client.post(
        "/api/v1/ai/job-description-autocomplete",
        headers={"Authorization": f"Bearer {token}"},
        json={"partial_description": "Please paint"},
    )

    assert response.status_code == 200
    assert response.json() == {"suggestion": ""}


def test_job_description_autocomplete_returns_empty_when_rate_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client)
    provider = FakeAIProvider(response="should not be used")
    app.dependency_overrides[get_ai_service] = lambda: AIService(primary=provider, fallback=provider)
    monkeypatch.setattr(ai_api, "consume_rate_limit", lambda *args, **kwargs: False)

    response = client.post(
        "/api/v1/ai/job-description-autocomplete",
        headers={"Authorization": f"Bearer {token}"},
        json={"partial_description": "Please paint"},
    )

    assert response.status_code == 200
    assert response.json() == {"suggestion": ""}
    assert provider.requests == []


def test_job_description_autocomplete_requires_consumer(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_api, "consume_rate_limit", lambda *args, **kwargs: True)

    response = client.post(
        "/api/v1/ai/job-description-autocomplete",
        json={"partial_description": "Please paint"},
    )

    assert response.status_code == 401
