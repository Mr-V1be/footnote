from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from snoska.domain.documents.formats import FormatRegistry, UnsupportedFormatError
from snoska.ports.checks.quality import ReferenceDocument, ReferenceSetError

LABELS_FILE = "labels.yaml"


def _text(entry: Mapping[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReferenceSetError(f"{where}: {key!r} must be a non-empty string")
    return value.strip()


class YamlReferenceSet:
    """The reference documents of a directory and their labels (labels.yaml).

    The labels are read when asked for, so a process that never runs the
    benchmark does not need the directory.
    """

    def __init__(self, directory: Path, formats: FormatRegistry) -> None:
        self._directory = directory
        self._formats = formats

    def documents(self) -> Sequence[ReferenceDocument]:
        labels = self._directory / LABELS_FILE
        if not labels.is_file():
            raise ReferenceSetError(f"no {LABELS_FILE} in {self._directory}")
        data = yaml.safe_load(labels.read_text(encoding="utf-8")) or {}
        entries = data.get("documents")
        if not isinstance(entries, list):
            raise ReferenceSetError(f"{labels}: 'documents' must be a list")
        documents = [self._document(entry) for entry in entries]
        names = [document.file_name for document in documents]
        if len(set(names)) != len(names):
            raise ReferenceSetError(f"{labels}: a document is listed twice")
        if sum(document.typical for document in documents) > 1:
            raise ReferenceSetError(f"{labels}: only one document can be typical")
        return documents

    async def content(self, document: ReferenceDocument) -> bytes:
        return await asyncio.to_thread((self._directory / document.file_name).read_bytes)

    def _document(self, entry: Mapping[str, Any]) -> ReferenceDocument:
        name = _text(entry, "file", LABELS_FILE)
        path = self._directory / name
        if not path.is_file():
            raise ReferenceSetError(f"{name}: the file is missing")
        with path.open("rb") as file:
            head = file.read(self._formats.signature_length)
        try:
            format_code = self._formats.detect(name, head).code
        except UnsupportedFormatError as exc:
            raise ReferenceSetError(f"{name}: {exc}") from exc
        violations = entry.get("violations")
        if not isinstance(violations, list) or not all(isinstance(v, str) for v in violations):
            raise ReferenceSetError(f"{name}: 'violations' must be a list of check codes")
        pages = entry.get("pages")
        if not isinstance(pages, int) or pages < 1:
            raise ReferenceSetError(f"{name}: 'pages' must be a positive number")
        return ReferenceDocument(
            file_name=name,
            title=_text(entry, "title", name),
            kind=_text(entry, "kind", name),
            format_code=format_code,
            pages=pages,
            expected=frozenset(violations),
            typical=bool(entry.get("typical", False)),
        )
