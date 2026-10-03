"""In-memory stand-ins for external providers."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from uuid import UUID, uuid4

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.domain.tenancy.members import Member
from snoska.ports.ai import Completion, CompletionRequest
from snoska.ports.identity import Invitation, OrganizationProfile
from snoska.ports.integrations.transport import TransportResult


class FakeDirectory:
    """The identity provider's organizations and members, in memory."""

    def __init__(self, organizations: Sequence[OrganizationProfile]) -> None:
        self._organizations = {org.id: org for org in organizations}
        self.members: dict[UUID, dict[UUID, Member]] = {org.id: {} for org in organizations}

    def add(self, organization_id: UUID, member: Member) -> None:
        self.members[organization_id][member.user_id] = member

    async def get_organization(self, organization_id: UUID) -> OrganizationProfile | None:
        return self._organizations.get(organization_id)

    async def list_members(self, organization_id: UUID) -> list[Member]:
        return list(self.members[organization_id].values())

    async def invite(self, organization_id: UUID, invitation: Invitation) -> UUID:
        user_id = uuid4()
        self.add(
            organization_id,
            Member(
                user_id=user_id,
                email=invitation.email,
                first_name=invitation.first_name,
                last_name=invitation.last_name,
                role_codes=frozenset({invitation.role_code}),
                pending=True,
            ),
        )
        return user_id

    async def set_role(self, organization_id: UUID, user_id: UUID, role_code: str) -> None:
        member = self.members[organization_id][user_id]
        self.members[organization_id][user_id] = replace(member, role_codes=frozenset({role_code}))

    async def remove(self, organization_id: UUID, user_id: UUID) -> None:
        self.members[organization_id].pop(user_id, None)


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


class RecordingTransport:
    """A webhook receiver that answers with the given status codes in turn
    (the last one repeats) and keeps what it was sent."""

    def __init__(self, *status_codes: int) -> None:
        self._codes = list(status_codes) or [204]
        self.sent: list[tuple[str, bytes, dict[str, str]]] = []

    def respond_with(self, *status_codes: int) -> None:
        self._codes = list(status_codes)

    async def post(self, url: str, body: bytes, headers: Mapping[str, str]) -> TransportResult:
        self.sent.append((url, body, dict(headers)))
        code = self._codes.pop(0) if len(self._codes) > 1 else self._codes[0]
        return TransportResult(status_code=code, duration_ms=3)
