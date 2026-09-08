from typing import Any

from google import genai
from google.genai import types

from app.ai.base import AIProvider
from app.ai.errors import AIProviderConfigurationError, AIProviderInvalidRequestError
from app.ai.models import AIRequest, AIResponse
from app.ai.providers.common import map_provider_error, usage_from_response


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: float = 30) -> None:
        self.model = model
        self._timeout = timeout
        self._client = genai.Client(api_key=api_key, http_options={"timeout": int(timeout * 1000)}) if api_key else None

    def generate(self, request: AIRequest) -> AIResponse:
        if self._client is None:
            raise AIProviderConfigurationError("gemini API key is not configured")
        if not request.prompt.strip():
            raise AIProviderInvalidRequestError("AI prompt must not be empty")
        try:
            contents: list[Any] = [request.prompt]
            contents.extend(types.Part.from_bytes(data=image.data, mime_type=image.mime_type) for image in request.images)
            config: dict[str, Any] = {}
            if request.system_instruction:
                config["system_instruction"] = request.system_instruction
            if request.structured:
                config["response_mime_type"] = "application/json"
            result = self._client.models.generate_content(model=self.model, contents=contents, config=config or None)
            return AIResponse(
                content=result.text or "",
                provider=self.name,
                model=self.model,
                structured=request.structured,
                usage=usage_from_response(result),
            )
        except (AIProviderConfigurationError, AIProviderInvalidRequestError):
            raise
        except Exception as error:
            raise map_provider_error(error, self.name) from error