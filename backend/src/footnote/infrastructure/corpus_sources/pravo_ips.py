from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

import httpx

from footnote.domain.corpus.acts import LegalAct
from footnote.infrastructure.corpus_sources.law_html import parse_law_html
from footnote.ports.clock import Clock
from footnote.ports.corpus.source import ActCatalog, CorpusSourceError, FetchedEdition

SOURCE_CODE = "pravo_ips"
# The portal serves documents in Windows-1251.
PORTAL_ENCODING = "cp1251"
_REVISION = re.compile(r"doc_itself=&nd=(\d+)&page=1&rdk=(\d+)")


@dataclass(frozen=True, slots=True)
class PravoIpsConfig:
    base_url: str = "http://pravo.gov.ru/proxy/ips/"
    timeout_seconds: float = 60.0


@dataclass(frozen=True, slots=True)
class RawEdition:
    revision: str
    html: bytes


class PravoIpsClient:
    """Reads the current redaction of a document from «Законодательство России»,
    the legal information system of the official portal pravo.gov.ru."""

    def __init__(self, client: httpx.AsyncClient, config: PravoIpsConfig) -> None:
        self._client = client
        self._config = config

    async def fetch(self, document_number: str) -> RawEdition:
        try:
            card = await self._client.get(
                self._config.base_url,
                params={"docbody": "", "nd": document_number},
                timeout=self._config.timeout_seconds,
            )
            card.raise_for_status()
            match = _REVISION.search(card.content.decode(PORTAL_ENCODING, errors="replace"))
            if match is None:
                raise CorpusSourceError("the portal page does not reference a document text")
            revision = match.group(2)
            body = await self._client.get(
                self._config.base_url,
                params={"doc_itself": "", "nd": document_number, "page": "1", "rdk": revision},
                timeout=self._config.timeout_seconds,
            )
            body.raise_for_status()
        except httpx.HTTPError as exc:
            raise CorpusSourceError(f"portal request failed: {exc!r}") from exc
        return RawEdition(revision=revision, html=body.content)


class PravoIpsSource:
    code = SOURCE_CODE

    def __init__(self, client: PravoIpsClient, catalog: ActCatalog, clock: Clock) -> None:
        self._client = client
        self._catalog = catalog
        self._clock = clock

    async def fetch_current(self, act: LegalAct) -> FetchedEdition:
        document_number = self._catalog.get(act.code).source_refs.get(SOURCE_CODE)
        if document_number is None:
            raise CorpusSourceError(f"act {act.code} has no reference on the portal")
        raw = await self._client.fetch(document_number)
        return edition_from_html(raw, self._clock.now())


def edition_from_html(raw: RawEdition, retrieved_at: datetime) -> FetchedEdition:
    law = parse_law_html(raw.html.decode(PORTAL_ENCODING))
    if not law.units:
        raise CorpusSourceError("no provisions found in the document text")
    return FetchedEdition(
        source_code=SOURCE_CODE,
        source_revision=raw.revision,
        amended_by=law.amended_by,
        retrieved_at=retrieved_at,
        units=law.units,
    )
