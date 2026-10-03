from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from snoska.domain.autofix.actions import AppliedChange, FixAction, FixPlan
from snoska.domain.documents.structure import DocumentStructure


@dataclass(frozen=True, slots=True)
class PatchResult:
    """The corrected file and what was changed in it. ``missed`` are the
    planned actions the file did not allow (text not found where expected)."""

    content: bytes
    changes: tuple[AppliedChange, ...]
    missed: tuple[FixAction, ...]


class DocumentPatcher(Protocol):
    """Applies a correction plan to a file of one format; the source file is
    never modified, a new one is produced."""

    format_code: str

    async def apply(
        self, content: bytes, plan: FixPlan, structure: DocumentStructure
    ) -> PatchResult: ...
