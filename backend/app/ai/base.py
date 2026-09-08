from abc import ABC, abstractmethod

from app.ai.models import AIRequest, AIResponse


class AIProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def generate(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError