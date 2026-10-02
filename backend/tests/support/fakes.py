"""In-memory stand-ins for external providers."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from uuid import UUID

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.ports.ai import Completion, CompletionRequest
from snoska.ports.identity import OrganizationProfile


class FakeDirectory:
    def __init__(self, organizations: Sequence[OrganizationProfile]) -> None:
        self._organizations = {org.id: org for org in organizations}

    async def get_organization(self, organization_id: UUID) -> OrganizationProfile | None:
        return self._organizations.get(organization_id)


class HashEmbedder:
    """Deterministic unit vectors: equal texts get equal vectors."""

    model = "hash-embedder"

    def __init__(self, space: EmbeddingSpace) -> None:
        self.space = space

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.space.dimensions:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            values.extend((byte - 127.5) / 127.5 for byte in digest)
            counter += 1
        vector = values[: self.space.dimensions]
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


_FRAGMENT = re.compile(r"^\[(D\d+)\] (?:\([^)]*\) )?(.+)$", re.MULTILINE)
_QUOTE_WORDS = 8


class RecordedLanguageModel:
    """A language model with recorded verdicts, keyed by words of the question.

    It answers like a well-behaved model: it quotes the first passage it was
    shown word for word and cites the first provision. ``verdicts`` maps a
    phrase of a check's question to the verdict to give; anything else is
    "present". Every request is kept for assertions.
    """

    model = "recorded"

    def __init__(self, verdicts: Mapping[str, str] | None = None) -> None:
        self._verdicts = dict(verdicts or {})
        self.requests: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> Completion:
        self.requests.append(request)
        prompt = request.messages[-1].content
        question = prompt.splitlines()[0]
        verdict = next(
            (verdict for phrase, verdict in self._verdicts.items() if phrase in question),
            "present",
        )
        fragments = _FRAGMENT.findall(prompt)
        quotes = (
            [
                {
                    "fragment": fragments[0][0],
                    "text": " ".join(fragments[0][1].split()[:_QUOTE_WORDS]),
                }
            ]
            if fragments and verdict in ("present", "partial")
            else []
        )
        answer = {
            "verdict": verdict,
            "quotes": quotes,
            "norm": "N1",
            "explanation": f"Записанный ответ: {verdict}.",
            "recommendation": "Дополните документ." if verdict in ("partial", "absent") else "",
        }
        return Completion(
            text=json.dumps(answer, ensure_ascii=False),
            model=self.model,
            prompt_tokens=None,
            completion_tokens=None,
        )
