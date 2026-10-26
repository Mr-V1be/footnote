from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from footnote.domain.corpus.embedding import content_hash
from footnote.domain.documents.structure import Block, BlockKind, DocumentStructure
from footnote.domain.shared.text import normalize_whitespace
from footnote.ports.ai import Embedder
from footnote.ports.checks.embeddings import EmbeddingCache

# Lines shorter than this are captions, numbers or signatures, not passages.
MIN_FRAGMENT_CHARS = 20
# A passage longer than this is cut for the model; the quote must lie within.
MAX_FRAGMENT_CHARS = 900
EMBED_BATCH = 16
# Cells of a table row as the model reads them; quote matching treats the
# separator as a space, so a quote across cells still matches the row.
CELL_SEPARATOR = " | "
# A header and at least one row.
MIN_TABLE_ROWS = 2
# How much a passage gains for each keyword it contains, on top of similarity.
KEYWORD_WEIGHT = 0.04
MAX_KEYWORD_BONUS = 0.12


@dataclass(frozen=True, slots=True)
class Fragment:
    """A passage of the document as the model sees it: the block's text, its
    number in the document and the heading of the section it belongs to.
    Quotes are taken from ``text`` only, which is the block's own text."""

    block_ordinal: int
    section: str | None
    label: str | None
    text: str

    @property
    def passage(self) -> str:
        """What is embedded: the section heading gives a short passage its topic."""
        return f"{self.section}\n{self.text}" if self.section else self.text


def _section_heading(block: Block) -> str:
    return " ".join(part for part in (block.label, block.text) if part)


def _row_text(cells: Sequence[str]) -> str:
    return CELL_SEPARATOR.join(normalize_whitespace(cell) for cell in cells)


def _table_fragments(block: Block, section: str | None) -> list[Fragment]:
    """A table reads row by row: each data row is a passage, the header names its columns."""
    rows = block.table.rows if block.table else ()
    if len(rows) < MIN_TABLE_ROWS:
        return []
    header = _row_text([cell.text for cell in rows[0]])
    context = f"{section} — {header}" if section else header
    fragments = []
    for row in rows[1:]:
        text = _row_text([cell.text for cell in row])
        if len(text) >= MIN_FRAGMENT_CHARS:
            fragments.append(Fragment(block.ordinal, context, None, text[:MAX_FRAGMENT_CHARS]))
    return fragments


def fragments_of(structure: DocumentStructure) -> list[Fragment]:
    fragments: list[Fragment] = []
    section: str | None = None
    for block in structure.blocks:
        if block.kind is BlockKind.HEADING:
            section = normalize_whitespace(_section_heading(block))
            continue
        if block.kind is BlockKind.TABLE:
            fragments.extend(_table_fragments(block, section))
            continue
        text = normalize_whitespace(block.text)
        if len(text) < MIN_FRAGMENT_CHARS:
            continue
        label = block.label.strip() if block.label else None
        fragments.append(Fragment(block.ordinal, section, label, text[:MAX_FRAGMENT_CHARS]))
    return fragments


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


async def embed_cached(
    texts: Sequence[str], embedder: Embedder, cache: EmbeddingCache
) -> dict[str, Sequence[float]]:
    """Vectors of texts by content hash, embedding only what the cache lacks."""
    hashes = {text: content_hash(text) for text in texts}
    known = dict(await cache.get_many(embedder.space, set(hashes.values())))
    missing = list(dict.fromkeys(text for text, digest in hashes.items() if digest not in known))
    fresh: dict[str, Sequence[float]] = {}
    for start in range(0, len(missing), EMBED_BATCH):
        batch = missing[start : start + EMBED_BATCH]
        vectors = await embedder.embed(batch)
        for text, vector in zip(batch, vectors, strict=True):
            embedder.space.validate(vector)
            fresh[hashes[text]] = vector
    if fresh:
        await cache.put_many(embedder.space, fresh)
        known.update(fresh)
    return {text: known[digest] for text, digest in hashes.items()}


class DocumentIndex:
    """Retrieval over the passages of one document version.

    Relevance is semantic similarity plus a small bonus for keywords of the
    requirement, so that a passage using the law's exact term is not missed
    when the wording of the requirement differs.
    """

    def __init__(self, fragments: Sequence[Fragment], vectors: dict[str, Sequence[float]]) -> None:
        self.fragments = tuple(fragments)
        self._vectors = vectors

    @classmethod
    async def build(
        cls, structure: DocumentStructure, embedder: Embedder, cache: EmbeddingCache
    ) -> DocumentIndex:
        fragments = fragments_of(structure)
        vectors = await embed_cached([fragment.passage for fragment in fragments], embedder, cache)
        return cls(fragments, vectors)

    def search(self, query: Sequence[float], keywords: Sequence[str], limit: int) -> list[Fragment]:
        """The most relevant passages, returned in reading order."""
        stems = [keyword.casefold() for keyword in keywords]
        scored: list[tuple[float, Fragment]] = []
        for fragment in self.fragments:
            similarity = _cosine(query, self._vectors[fragment.passage])
            text = fragment.passage.casefold()
            bonus = min(
                MAX_KEYWORD_BONUS, KEYWORD_WEIGHT * sum(1 for stem in stems if stem in text)
            )
            scored.append((similarity + bonus, fragment))
        best = sorted(scored, key=lambda item: item[0], reverse=True)[:limit]
        return sorted((fragment for _, fragment in best), key=lambda item: item.block_ordinal)
