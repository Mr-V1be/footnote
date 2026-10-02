from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from snoska.domain.corpus.embedding import EmbeddingSpace


class AiProviderError(Exception):
    """The model provider failed or is unreachable; the call may be retried."""


class Embedder(Protocol):
    space: EmbeddingSpace
    model: str

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: MessageRole
    content: str


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    messages: tuple[ChatMessage, ...]
    # JSON Schema the answer must conform to; None for free text.
    response_schema: Mapping[str, Any] | None = None
    temperature: float = 0.0
    max_tokens: int = 1024
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Completion:
    text: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None


class LanguageModel(Protocol):
    model: str

    async def complete(self, request: CompletionRequest) -> Completion: ...
