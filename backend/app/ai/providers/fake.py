from collections.abc import Callable
from typing import Any

from app.ai.base import AIProvider
from app.ai.models import AIRequest, AIResponse


class FakeAIProvider(AIProvider):
    name = "fake"

    def __init__(
        self,
        model: str = "fake-model",
        response: str = "fake response",
        error: Exception | None = None,
        responder: Callable[[AIRequest], str] | None = None,
    ) -> None:
        self.model = model
        self.response = response
        self.error = error
        self.responder = responder
        self.requests: list[AIRequest] = []

    def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        if self.error:
            raise self.error
        content = self.responder(request) if self.responder else self.response
        return AIResponse(content=content, provider=self.name, model=self.model, structured=request.structured)