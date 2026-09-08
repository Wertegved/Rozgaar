from typing import Any

from app.ai.errors import (
    AIProviderConfigurationError,
    AIProviderInvalidRequestError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)


def map_provider_error(error: Exception, provider: str) -> Exception:
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    message = str(error).lower()
    prefix = f"{provider} provider request failed"
    if isinstance(error, (TimeoutError,)) or "timeout" in message:
        return AIProviderTimeoutError(prefix)
    if status == 429 or "rate limit" in message or "quota" in message:
        return AIProviderRateLimitError(prefix)
    if status in {400, 422}:
        return AIProviderInvalidRequestError(prefix)
    if status in {401, 403} or "api key" in message or "authentication" in message:
        return AIProviderConfigurationError(prefix)
    if isinstance(status, int) and status >= 500:
        return AIProviderUnavailableError(prefix)
    return AIProviderUnavailableError(prefix)


def usage_from_response(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        return usage.model_dump(exclude_none=True)
    if isinstance(usage, dict):
        return dict(usage)
    return {
        key: value
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if (value := getattr(usage, key, None)) is not None
    }