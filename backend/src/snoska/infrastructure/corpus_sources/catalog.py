from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from snoska.domain.corpus.acts import ActKind, LegalAct
from snoska.domain.shared.errors import NotFoundError
from snoska.ports.corpus_source import TrackedAct


class UnknownActError(NotFoundError):
    code = "unknown_act"


@dataclass(frozen=True, slots=True)
class SnapshotRef:
    """A copy of a source document bundled with the release for offline seeding."""

    path: Path
    source_code: str
    revision: str
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    tracked: TrackedAct
    snapshot: SnapshotRef | None


class YamlActCatalog:
    """The acts the corpus tracks, declared as data in ``acts.yaml``."""

    def __init__(self, path: Path) -> None:
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._entries: dict[str, CatalogEntry] = {}
        for raw in data["acts"]:
            act = LegalAct(
                code=raw["code"],
                kind=ActKind(raw["kind"]),
                short_title=raw["short_title"],
                title=raw["title"],
                adopted_on=date.fromisoformat(str(raw["adopted_on"])),
            )
            snapshot = raw.get("snapshot")
            self._entries[act.code] = CatalogEntry(
                tracked=TrackedAct(act=act, source_refs=dict(raw.get("sources", {}))),
                snapshot=(
                    SnapshotRef(
                        path=path.parent / snapshot["file"],
                        source_code=snapshot["source"],
                        revision=str(snapshot["revision"]),
                        retrieved_at=datetime.fromisoformat(str(snapshot["retrieved_at"])),
                    )
                    if snapshot
                    else None
                ),
            )

    def get(self, act_code: str) -> TrackedAct:
        return self.entry(act_code).tracked

    def all(self) -> tuple[TrackedAct, ...]:
        return tuple(entry.tracked for entry in self._entries.values())

    def entry(self, act_code: str) -> CatalogEntry:
        try:
            return self._entries[act_code]
        except KeyError as exc:
            raise UnknownActError(f"act {act_code!r} is not tracked") from exc
