from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from footnote.domain.shared.errors import ValidationError


class UnknownDocumentKindError(ValidationError):
    code = "unknown_document_kind"


@dataclass(frozen=True, slots=True)
class DocumentKind:
    """A category of document. Checks attach to kinds, labels live in translations."""

    code: str
    rank: int


class DocumentKindRegistry:
    def __init__(self, kinds: Iterable[DocumentKind], default: str) -> None:
        self._kinds = {kind.code: kind for kind in kinds}
        if default not in self._kinds:
            raise ValueError(f"default kind {default!r} is not registered")
        self.default = self._kinds[default]

    def get(self, code: str) -> DocumentKind:
        try:
            return self._kinds[code]
        except KeyError as exc:
            raise UnknownDocumentKindError(f"unknown document kind {code!r}") from exc

    def all(self) -> tuple[DocumentKind, ...]:
        return tuple(sorted(self._kinds.values(), key=lambda kind: kind.rank))


DOCUMENT_KINDS = DocumentKindRegistry(
    [
        DocumentKind(code="pd_policy", rank=0),
        DocumentKind(code="pd_consent", rank=1),
        DocumentKind(code="pd_assignment", rank=2),
        DocumentKind(code="contract", rank=3),
        DocumentKind(code="regulation", rank=4),
        DocumentKind(code="order", rank=5),
        DocumentKind(code="other", rank=6),
    ],
    default="other",
)
