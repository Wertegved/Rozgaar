import pytest
from pydantic import BaseModel

from app.ai.errors import (
    AIProviderConfigurationError,
    AIProviderInvalidRequestError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    AIStructuredOutputError,
)
from app.ai.models import AIImageInput, AIRequest
from app.ai.providers.fake import FakeAIProvider
from app.ai.service import AIService
from app.core.config import Settings


class Classification(BaseModel):
    label: str
    confidence: float


def test_phase15_configuration_defaults_and_empty_keys() -> None:
    settings = Settings(_env_file=None)

    assert settings.ai_primary_provider == "groq"
    assert settings.ai_primary_model == "meta-llama/llama-4-scout-17b-16e-instruct"
    assert settings.ai_fallback_provider == "gemini"
    assert settings.ai_fallback_model == "gemini-3.8-flash"
    assert settings.groq_api_key == ""
    assert settings.gemini_api_key == ""
    assert settings.ai_request_timeout_seconds == 30
    assert settings.ai_max_retries == 2


def test_invalid_provider_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="AI provider"):
        Settings(ai_primary_provider="unknown", _env_file=None)


def test_primary_provider_success_and_metadata() -> None:
    primary = FakeAIProvider(model="primary-model", response="answer")
    fallback = FakeAIProvider(model="fallback-model", response="fallback")

    response = AIService(primary=primary, fallback=fallback).generate(AIRequest("question"))

    assert response.content == "answer"
    assert response.provider == "fake"
    assert response.model == "primary-model"
    assert response.request_id
    assert len(primary.requests) == 1
    assert fallback.requests == []


@pytest.mark.parametrize(
    "error",
    [AIProviderRateLimitError("rate"), AIProviderTimeoutError("timeout"), AIProviderUnavailableError("down")],
)
def test_transient_primary_failure_falls_back_without_infinite_loop(error: Exception) -> None:
    primary = FakeAIProvider(error=error)
    fallback = FakeAIProvider(response="fallback")

    response = AIService(primary=primary, fallback=fallback).generate(AIRequest("question"))

    assert response.content == "fallback"
    assert len(primary.requests) == 3
    assert len(fallback.requests) == 1


def test_permanent_primary_failure_does_not_fallback() -> None:
    primary = FakeAIProvider(error=AIProviderInvalidRequestError("invalid"))
    fallback = FakeAIProvider(response="fallback")

    with pytest.raises(AIProviderInvalidRequestError):
        AIService(primary=primary, fallback=fallback).generate(AIRequest("question"))

    assert fallback.requests == []
    assert len(primary.requests) == 1


def test_configuration_failure_does_not_fallback() -> None:
    primary = FakeAIProvider(error=AIProviderConfigurationError("not configured"))
    fallback = FakeAIProvider(response="fallback")

    with pytest.raises(AIProviderConfigurationError):
        AIService(primary=primary, fallback=fallback).generate(AIRequest("question"))

    assert fallback.requests == []


def test_both_providers_unavailable_returns_normalized_failure() -> None:
    primary = FakeAIProvider(error=AIProviderUnavailableError("primary down"))
    fallback = FakeAIProvider(error=AIProviderUnavailableError("fallback down"))

    with pytest.raises(AIProviderUnavailableError, match="fallback down"):
        AIService(primary=primary, fallback=fallback).generate(AIRequest("question"))


def test_structured_output_is_validated() -> None:
    service = AIService(
        primary=FakeAIProvider(response='{"label":"safe","confidence":0.9}'),
        fallback=FakeAIProvider(),
    )

    result = service.generate_structured(AIRequest("classify"), Classification)

    assert result.label == "safe"
    assert result.confidence == 0.9


def test_malformed_structured_output_is_rejected() -> None:
    service = AIService(primary=FakeAIProvider(response="not-json"), fallback=FakeAIProvider())

    with pytest.raises(AIStructuredOutputError):
        service.generate_structured(AIRequest("classify"), Classification)


def test_fake_provider_supports_multimodal_requests() -> None:
    provider = FakeAIProvider(response='{"ok":true}')
    request = AIRequest(
        prompt="inspect",
        system_instruction="be concise",
        images=(AIImageInput(mime_type="image/png", data=b"pixels"),),
        structured=True,
    )

    response = provider.generate(request)

    assert response.content == '{"ok":true}'
    assert provider.requests[0].images[0].data == b"pixels"
    assert provider.requests[0].structured is True


def test_keyless_sdk_providers_fail_without_exposing_credentials() -> None:
    from app.ai.providers.gemini import GeminiProvider
    from app.ai.providers.groq import GroqProvider

    for provider in (GroqProvider("", "model"), GeminiProvider("", "model")):
        with pytest.raises(AIProviderConfigurationError) as error:
            provider.generate(AIRequest("question"))
        assert "key" in str(error.value).lower()
        assert "sk-" not in str(error.value)