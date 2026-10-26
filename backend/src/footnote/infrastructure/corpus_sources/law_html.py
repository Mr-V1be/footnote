from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import html as lxml_html
from lxml.etree import _Element

from footnote.domain.corpus.units import ParsedUnit, UnitKind
from footnote.domain.shared.text import normalize_whitespace

_CHAPTER = re.compile(r"^Глава\s+(\d+(?:\.\d+)?)\.?\s*(.*)$")
_ARTICLE = re.compile(r"^Статья\s+(\d+(?:\.\d+)?)\.?\s*(.*)$")
_PART = re.compile(r"^(\d+(?:\.\d+)?)\.(?:\s+(.*)|)$", re.DOTALL)
_CLAUSE = re.compile(r"^(\d+(?:\.\d+)?)\)(?:\s*(.*)|)$", re.DOTALL)
_SUBCLAUSE = re.compile(r"^([а-я](?:\.\d+)?)\)(?:\s*(.*)|)$", re.DOTALL)
_ARTICLE_NOTE = re.compile(r"стать(?:ей|ю|и)\b|^\(Наименование", re.IGNORECASE)
_CHAPTER_NOTE = re.compile(r"глав(?:ой|ы|у)\b", re.IGNORECASE)
_NOTE = re.compile(r"\((?:[^()]|\([^()]*\))*\)\s*$")
_REPEALED = re.compile(r"утратил[аио]?\s+силу", re.IGNORECASE)
_AMENDMENT = re.compile(r"от\s+(\d{2}\.\d{2}\.\d{4})\s+№\s+([\d-]+-ФЗ)")
_SIGNATURE_START = "Президент Российской Федерации"


@dataclass(slots=True)
class _Node:
    kind: UnitKind
    number: str | None
    heading: str | None
    text: str
    notes: list[str] = field(default_factory=list)
    repealed: bool = False
    children: list[_Node] = field(default_factory=list)

    def freeze(self) -> ParsedUnit:
        return ParsedUnit(
            kind=self.kind,
            number=self.number,
            heading=self.heading,
            text=self.text,
            notes=tuple(self.notes),
            repealed=self.repealed,
            children=tuple(child.freeze() for child in self.children),
        )


@dataclass(frozen=True, slots=True)
class ParsedLaw:
    units: tuple[ParsedUnit, ...]
    amended_by: str | None


def _text(element: _Element) -> str:
    return "".join(str(part) for part in element.itertext())


def _prepare(root: _Element) -> None:
    """Superscript numbers (``18<sup>1</sup>``) become dotted (``18.1``)."""
    for span in root.iter("span"):
        if span.get("class") == "W9" and span.text:
            span.text = f".{span.text.strip()}"


def _split_notes(paragraph: _Element) -> tuple[str, list[str]]:
    notes: list[str] = []
    for mark in list(paragraph.iter("span")):
        if mark.get("class") != "mark":
            continue
        note = normalize_whitespace(_text(mark))
        if note:
            notes.append(note)
        parent = mark.getparent()
        if parent is not None:
            tail = mark.tail or ""
            previous = mark.getprevious()
            if previous is not None:
                previous.tail = (previous.tail or "") + tail
            else:
                parent.text = (parent.text or "") + tail
            parent.remove(mark)
    text = normalize_whitespace(_text(paragraph))
    # Notes typed in plain text at the end of a provision, e.g. «(Утратил силу - …)».
    while (match := _NOTE.search(text)) and (
        _REPEALED.search(match.group(0)) or "Федеральн" in match.group(0)
    ):
        notes.insert(0, match.group(0).strip())
        text = text[: match.start()].rstrip()
    return text, notes


def _amended_by(root: _Element) -> str | None:
    for paragraph in root.iter("p"):
        content = normalize_whitespace(_text(paragraph))
        if paragraph.get("class") == "C" and "В редакции" in content:
            found = _AMENDMENT.findall(content)
            if found:
                date, number = found[-1]
                return f"от {date} № {number}"
    return None


class _TreeBuilder:
    def __init__(self) -> None:
        self.roots: list[_Node] = []
        self._chapter: _Node | None = None
        self._article: _Node | None = None
        self._part: _Node | None = None
        self._clause: _Node | None = None
        self._lead_in: _Node | None = None
        self._last: _Node | None = None

    def _attach(self, parent: _Node | None, node: _Node) -> _Node:
        (parent.children if parent is not None else self.roots).append(node)
        self._last = node
        return node

    def heading(self, text: str, notes: list[str]) -> None:
        if match := _CHAPTER.match(text):
            node = _Node(UnitKind.CHAPTER, match.group(1), match.group(2) or None, "", notes)
            self._chapter = self._attach(None, node)
            self._article = self._part = self._clause = self._lead_in = None
        elif match := _ARTICLE.match(text):
            heading = match.group(2) or None
            node = _Node(UnitKind.ARTICLE, match.group(1), heading, "", notes)
            node.repealed = bool(heading and _REPEALED.search(heading)) or any(
                _REPEALED.search(note) for note in notes
            )
            self._article = self._attach(self._chapter, node)
            self._part = self._clause = self._lead_in = None

    def note(self, text: str) -> None:
        """Attach an editorial note to the provision it speaks about."""
        if _CHAPTER_NOTE.search(text) and self._chapter is not None and self._article is None:
            target: _Node | None = self._chapter
        elif _ARTICLE_NOTE.search(text) and self._article is not None:
            target = self._article
        else:
            target = self._last
        if target is not None:
            target.notes.append(text)

    def provision(self, text: str, notes: list[str]) -> None:
        if self._article is None:
            return
        repealed = (not text or text.startswith("(")) and any(_REPEALED.search(n) for n in notes)
        if match := _SUBCLAUSE.match(text):
            parent = self._clause or self._part or self._article
            self._attach(parent, self._node(UnitKind.SUBCLAUSE, match, notes, repealed))
        elif match := _CLAUSE.match(text):
            parent = self._lead_in or self._part or self._article
            self._clause = self._attach(parent, self._node(UnitKind.CLAUSE, match, notes, repealed))
        elif match := _PART.match(text):
            self._part = self._attach(
                self._article, self._node(UnitKind.PART, match, notes, repealed)
            )
            self._clause = self._lead_in = None
        else:
            parent = self._part or self._article
            node = self._attach(parent, _Node(UnitKind.PARAGRAPH, None, None, text, notes))
            self._clause = None
            # An unnumbered sentence ending with a colon introduces the list
            # that follows («…используются следующие основные понятия:»).
            self._lead_in = node if text.endswith(":") else None

    @staticmethod
    def _node(kind: UnitKind, match: re.Match[str], notes: list[str], repealed: bool) -> _Node:
        body = (match.group(2) or "").strip()
        if body.startswith("(") and _REPEALED.search(body):
            notes = [body, *notes]
            body = ""
        return _Node(
            kind, match.group(1), None, body, notes, repealed or (not body and bool(notes))
        )


def parse_law_html(document: str) -> ParsedLaw:
    """Parses a law as published by the official legal information portal."""
    root = lxml_html.fromstring(document)
    _prepare(root)
    builder = _TreeBuilder()
    started = False
    for paragraph in root.iter("p"):
        css = paragraph.get("class")
        text, notes = _split_notes(paragraph)
        if css == "H":
            if _CHAPTER.match(text) or _ARTICLE.match(text):
                started = True
                builder.heading(text, notes)
            continue
        if not started:
            continue
        if text.startswith(_SIGNATURE_START):
            break
        if css == "P" or (not text and notes):
            for note in [text, *notes] if text else notes:
                builder.note(note)
            continue
        if text:
            builder.provision(text, notes)
    return ParsedLaw(
        units=tuple(root_node.freeze() for root_node in builder.roots),
        amended_by=_amended_by(root),
    )
