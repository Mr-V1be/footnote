from __future__ import annotations

import gzip

import anyio

from snoska.domain.corpus.acts import LegalAct
from snoska.infrastructure.corpus_sources.catalog import YamlActCatalog
from snoska.infrastructure.corpus_sources.pravo_ips import (
    SOURCE_CODE,
    RawEdition,
    edition_from_html,
)
from snoska.ports.corpus_source import CorpusSourceError, FetchedEdition


class SnapshotSource:
    """Serves the bundled copy of a portal document.

    The snapshot holds the portal's own bytes, so it yields exactly the
    edition the live source would; syncing from either is idempotent.
    """

    code = "snapshot"

    def __init__(self, catalog: YamlActCatalog) -> None:
        self._catalog = catalog

    async def fetch_current(self, act: LegalAct) -> FetchedEdition:
        snapshot = self._catalog.entry(act.code).snapshot
        if snapshot is None or snapshot.source_code != SOURCE_CODE:
            raise CorpusSourceError(f"no bundled snapshot for {act.code}")
        compressed = await anyio.Path(snapshot.path).read_bytes()
        raw = RawEdition(revision=snapshot.revision, html=gzip.decompress(compressed))
        return edition_from_html(raw, snapshot.retrieved_at)
