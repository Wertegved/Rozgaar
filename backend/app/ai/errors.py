class AIProviderError(Exception):
    """Base error for failures returned by an AI provider."""


class AIProviderRateLimitError(AIProviderError):
    pass


class AIProviderTimeoutError(AIProviderError):
    pass


class AIProviderUnavailableError(AIProviderError):
    pass


class AIProviderConfigurationError(AIProviderError):
    pass


class AIProviderInvalidRequestError(AIProviderError):
    pass


class AIStructuredOutputError(AIProviderError):
    pass