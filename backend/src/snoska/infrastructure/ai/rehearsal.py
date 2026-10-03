"""The rehearsal provider: answers made by rules from the text shown, no model.

It exists for one purpose — preparing demo materials (screens, video) before
a model API is connected — and is never a default. Nothing here is a neural
network or runs one: the embedder hashes word stems into a vector (so texts
that share words are near each other), and the "language model" decides by
the overlap of words between a requirement and the passages it is given,
quoting them verbatim so that every answer passes the same grounding checks
as a real model's. Each explanation says it is a draft.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence

from snoska.domain.corpus.embedding import EmbeddingSpace
from snoska.ports.ai import Completion, CompletionRequest

REHEARSAL_MODEL = "черновой адаптер"
REHEARSAL_SPACE = EmbeddingSpace(code="rehearsal-512", dimensions=512)

_WORD = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)
# Words shorter than this carry little meaning (prepositions, conjunctions).
_MIN_WORD = 5
# Russian inflects word endings: a stem of this length matches the forms.
_STEM = 6
_QUOTE_WORDS = 12
_FRAGMENT = re.compile(r"^\[(D\d+)\] (?:\([^)]*\) )?(.+)$", re.MULTILINE)
_NORM = re.compile(r"^\[(N\d+)\] ", re.MULTILINE)
_PROVISION = re.compile(r"^(N\d+) \(([^)]*)\):\n(.+)$", re.MULTILINE)
# Overlap of stems with the requirement that counts as "said in the document".
_PRESENT_OVERLAP = 3
_PARTIAL_OVERLAP = 1
DRAFT = "Черновик без модели"


def stems(text: str) -> set[str]:
    return {word.lower()[:_STEM] for word in _WORD.findall(text) if len(word) >= _MIN_WORD}


def _quote(text: str) -> str:
    return " ".join(text.split()[:_QUOTE_WORDS])


class FeatureHashEmbedder:
    """Word stems hashed into a fixed-size vector, normalised: cosine
    similarity then follows the words two texts share."""

    model = REHEARSAL_MODEL
    space = REHEARSAL_SPACE

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.space.dimensions
        for stem in stems(text):
            digest = hashlib.sha256(stem.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.space.dimensions
            vector[index] += 1.0 if digest[4] % 2 else -1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            vector[0], norm = 1.0, 1.0
        return [value / norm for value in vector]


class RehearsalLanguageModel:
    """Answers the two kinds of requests the product makes — a legal check
    and a question to the norm — in their JSON schemas, by word overlap."""

    model = REHEARSAL_MODEL

    async def complete(self, request: CompletionRequest) -> Completion:
        schema = json.dumps(request.response_schema or {}, ensure_ascii=False)
        answer = self._question(request) if "citations" in schema else self._check(request)
        return Completion(
            text=json.dumps(answer, ensure_ascii=False),
            model=self.model,
            prompt_tokens=None,
            completion_tokens=None,
        )

    @staticmethod
    def _check(request: CompletionRequest) -> Mapping[str, object]:
        prompt = next(m.content for m in request.messages if m.role.value == "user")
        lines = prompt.splitlines()
        requirement = " ".join(lines[:2])
        wanted = stems(requirement)
        fragments = _FRAGMENT.findall(prompt)
        norm = (_NORM.findall(prompt) or ["N1"])[0]
        scored = sorted(
            ((len(wanted & stems(text)), key, text) for key, text in fragments),
            key=lambda item: -item[0],
        )
        best = scored[0] if scored else (0, "", "")
        overlap, key, text = best
        if overlap >= _PRESENT_OVERLAP:
            verdict, recommendation = "present", ""
            explanation = f"{DRAFT}: в документе есть фрагмент на эту тему."
        elif overlap >= _PARTIAL_OVERLAP:
            verdict = "partial"
            explanation = f"{DRAFT}: тема затронута, но не раскрыта полностью."
            recommendation = "Раскройте требование в документе подробнее."
        else:
            verdict = "absent"
            explanation = f"{DRAFT}: во фрагментах документа этого не нашлось."
            recommendation = "Добавьте в документ положение об этом."
        quotes = [{"fragment": key, "text": _quote(text)}] if verdict != "absent" and key else []
        return {
            "verdict": verdict,
            "quotes": quotes,
            "norm": norm,
            "explanation": explanation,
            "recommendation": recommendation,
        }

    @staticmethod
    def _question(request: CompletionRequest) -> Mapping[str, object]:
        prompt = next(m.content for m in request.messages if m.role.value == "user")
        question = prompt.splitlines()[0].removeprefix("Вопрос:").strip()
        wanted = stems(question)
        provisions = sorted(
            ((len(wanted & stems(text)), key, text) for key, _, text in _PROVISION.findall(prompt)),
            key=lambda item: -item[0],
        )
        if not provisions or provisions[0][0] == 0:
            return {"found": False, "answer": "", "citations": []}
        _, key, text = provisions[0]
        quote = _quote(text)
        return {
            "found": True,
            "answer": f"{DRAFT}. Ближе всего к вопросу это положение: «{quote}…» [1].",
            "citations": [{"norm": key, "quote": quote}],
        }
