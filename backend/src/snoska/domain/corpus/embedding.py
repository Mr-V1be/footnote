from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from snoska.domain.corpus.units import UnitKind
from snoska.domain.shared.errors import ValidationError
from snoska.domain.shared.text import normalize_text


class DimensionMismatchError(ValidationError):
    code = "embedding_dimension_mismatch"


@dataclass(frozen=True, slots=True)
class EmbeddingSpace:
    """A vector space: vectors are comparable only within one space."""

    code: str
    dimensions: int

    def validate(self, vector: Sequence[float]) -> None:
        if len(vector) != self.dimensions:
            raise DimensionMismatchError(
                f"space {self.code} expects {self.dimensions} dimensions, got {len(vector)}"
            )


# Units that carry normative text of their own. Chapters and articles are
# represented through their headings in the context of their descendants.
EMBEDDABLE_KINDS = frozenset(
    {UnitKind.PART, UnitKind.CLAUSE, UnitKind.SUBCLAUSE, UnitKind.PARAGRAPH}
)


def embedding_text(
    citation: str, headings: Sequence[str], lead_ins: Sequence[str], text: str
) -> str:
    """Self-contained passage for retrieval: the provision with the article
    heading and the lead-in sentences of its parents (``…в случаях:``)."""
    lines = [citation, *headings, *lead_ins, text]
    return "\n".join(normalize_text(line) for line in lines if line.strip())


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
