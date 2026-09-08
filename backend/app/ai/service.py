import json
from typing import TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from app.ai.base import AIProvider
from app.ai.errors import (
    AIProviderConfigurationError,
    AIProviderInvalidRequestError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    AIStructuredOutputError,
)
from app.ai.models import AIRequest, AIResponse
from app.ai.providers.fake import FakeAIProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.groq import GroqProvider
from app.core.config import Settings, get_settings


StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
_FALLBACK_ERRORS = (AIProviderRateLimitError, AIProviderTimeoutError, AIProviderUnavailableError)


class AIService:
    def __init__(
        self,
        primary: AIProvider | None = None,
        fallback: AIProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        configuration = settings or get_settings()
        self.max_retries = configuration.ai_max_retries
        self.primary = primary or _provider_from_settings(
            configuration.ai_primary_provider,
            configuration.ai_primary_model,
            configuration,
        )
        self.fallback = fallback or _provider_from_settings(
            configuration.ai_fallback_provider,
            configuration.ai_fallback_model,
            configuration,
        )

    def generate(self, request: AIRequest) -> AIResponse:
        request_id = str(uuid4())
        try:
            response = self._attempt(self.primary, request)
            return _with_request_id(response, request_id)
        except _FALLBACK_ERRORS:
            if self.fallback is self.primary:
                raise
            response = self._attempt(self.fallback, request)
            return _with_request_id(response, request_id)

    def generate_structured(self, request: AIRequest, response_model: type[StructuredModel]) -> StructuredModel:
        response = self.generate(
            AIRequest(
                prompt=request.prompt,
                system_instruction=request.system_instruction,
                images=request.images,
                structured=True,
            )
        )
        try:
            return response_model.model_validate(json.loads(response.content))
        except (json.JSONDecodeError, ValidationError, TypeError) as error:
            raise AIStructuredOutputError("AI provider returned malformed structured output") from error

    def _attempt(self, provider: AIProvider, request: AIRequest) -> AIResponse:
        attempts = 1 + self.max_retries
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                return provider.generate(request)
            except _FALLBACK_ERRORS as error:
                last_error = error
        if last_error is not None:
            raise last_error
        raise AIProviderUnavailableError("AI provider request failed")


def _provider_from_settings(name: str, model: str, settings: Settings) -> AIProvider:
    if name == "groq":
        return GroqProvider(settings.groq_api_key, model, settings.ai_request_timeout_seconds)
    if name == "gemini":
        return GeminiProvider(settings.gemini_api_key, model, settings.ai_request_timeout_seconds)
    if name == "fake":
        return FakeAIProvider(model=model)
    raise AIProviderConfigurationError(f"Unsupported AI provider: {name}")


def _with_request_id(response: AIResponse, request_id: str) -> AIResponse:
    return AIResponse(
        content=response.content,
        provider=response.provider,
        model=response.model,
        structured=response.structured,
        usage=response.usage,
        request_id=request_id,
    )