from typing import Any

from groq import Groq

from app.ai.base import AIProvider
from app.ai.errors import AIProviderConfigurationError, AIProviderInvalidRequestError
from app.ai.models import AIRequest, AIResponse
from app.ai.providers.common import map_provider_error, usage_from_response


class GroqProvider(AIProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str, timeout: float = 30) -> None:
        self.model = model
        self._timeout = timeout
        self._client = Groq(api_key=api_key, timeout=timeout) if api_key else None

    def generate(self, request: AIRequest) -> AIResponse:
        if self._client is None:
            raise AIProviderConfigurationError("groq API key is not configured")
        if not request.prompt.strip():
            raise AIProviderInvalidRequestError("AI prompt must not be empty")
        try:
            messages: list[dict[str, Any]] = []
            if request.system_instruction:
                messages.append({"role": "system", "content": request.system_instruction})
            content: Any = request.prompt
            if request.images:
                content = [{"type": "text", "text": request.prompt}]
                content.extend(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{image.mime_type};base64,{_encode(image.data)}"},
                    }
                    for image in request.images
                )
            messages.append({"role": "user", "content": content})
            options: dict[str, Any] = {"model": self.model, "messages": messages}
            if request.structured:
                options["response_format"] = {"type": "json_object"}
            result = self._client.chat.completions.create(**options)
            return AIResponse(
                content=result.choices[0].message.content or "",
                provider=self.name,
                model=self.model,
                structured=request.structured,
                usage=usage_from_response(result),
            )
        except (AIProviderConfigurationError, AIProviderInvalidRequestError):
            raise
        except Exception as error:
            raise map_provider_error(error, self.name) from error


def _encode(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")