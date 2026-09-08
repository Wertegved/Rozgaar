from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True)
class AIImageInput:
    mime_type: str
    data: bytes


@dataclass(frozen=True)
class AIRequest:
    prompt: str
    system_instruction: str | None = None
    images: tuple[AIImageInput, ...] = ()
    structured: bool = False


@dataclass(frozen=True)
class AIResponse:
    content: str
    provider: str
    model: str
    structured: bool = False
    usage: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None


class AIProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
