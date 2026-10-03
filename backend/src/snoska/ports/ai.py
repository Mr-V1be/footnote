from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from snoska.domain.corpus.embedding import EmbeddingSpace


class AiProviderError(Exception):
    """The model provider failed or is unreachable; the call may be retried."""


class ModelNotConfiguredError(AiProviderError):
    """No model API is configured for this installation: nothing to retry."""


class ModelBudgetExhaustedError(AiProviderError):
    """The requests the model allows today are spent: checks wait for the
    budget to renew (or for an administrator to connect a paid model)."""


class ModelOutputError(AiProviderError):
    """The provider answered, but not in the form the request demanded
    (e.g. no JSON object for a structured request). Asking again can help."""


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


class RequestBudget(Protocol):
    """How many model requests may still be made: a per-minute pace and a
    daily allowance, shared by every process of the installation."""

    async def spend(self) -> None:
        """Take one request; wait for the minute to pass if the pace is
        reached, raise ModelBudgetExhaustedError if the day's allowance is."""
        ...

    async def refund(self) -> None:
        """Give back a request the provider refused without serving it (a
        busy model, a model it no longer serves): it does not count it."""
        ...

    async def remaining_today(self) -> int | None:
        """Requests left today; None when there is no daily allowance."""
        ...


class CompletionCache(Protocol):
    """Answers of the model kept by the request that produced them: the same
    request (same text, checks, prompt and models) is never paid twice."""

    async def get(self, key: str) -> Completion | None: ...

    async def put(self, key: str, completion: Completion) -> None: ...
