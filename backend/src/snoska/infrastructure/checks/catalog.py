from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from snoska.domain.checks.catalog import (
    CatalogError,
    CheckCatalog,
    CheckDefinition,
    CheckFamily,
    CheckMethod,
    LawNorm,
    ModelBrief,
    Norm,
    Severity,
    StandardNorm,
)
from snoska.domain.checks.rules.base import RuleParams
from snoska.domain.checks.rules.registry import RuleRegistry
from snoska.domain.checks.spread import SpreadPolicy
from snoska.domain.documents.kinds import DocumentKindRegistry, UnknownDocumentKindError

REVISION_LENGTH = 12


def _text(entry: Mapping[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{where}: {key!r} must be a non-empty string")
    return value.strip()


def _norm(family: Mapping[str, Any], entry: Mapping[str, Any], code: str) -> Norm:
    if "anchors" in entry:
        act = _text(family, "act", code)
        anchors = entry["anchors"]
        if not isinstance(anchors, list) or not all(isinstance(item, str) for item in anchors):
            raise CatalogError(f"{code}: anchors must be a list of strings")
        return LawNorm(act_code=act, anchors=tuple(anchors))
    return StandardNorm(
        standard=_text(family, "standard", code), clause=_text(entry, "clause", code)
    )


def _brief(entry: Mapping[str, Any], code: str) -> ModelBrief | None:
    raw = entry.get("brief")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise CatalogError(f"{code}: brief must be a mapping")
    keywords = raw.get("keywords", [])
    if not isinstance(keywords, list) or not all(isinstance(item, str) for item in keywords):
        raise CatalogError(f"{code}: brief.keywords must be a list of strings")
    return ModelBrief(
        question=_text(raw, "question", code),
        criteria=_text(raw, "criteria", code),
        search=_text(raw, "search", code),
        keywords=tuple(keywords),
    )


def _spread(raw: object, base: SpreadPolicy, where: str) -> SpreadPolicy:
    """A family's default thresholds, overridden field by field by a check."""
    if raw is None:
        return base
    if not isinstance(raw, dict) or not set(raw) <= {"share", "min_places", "max_local"}:
        raise CatalogError(f"{where}: spread takes share, min_places and max_local")
    try:
        return SpreadPolicy(
            share=float(raw.get("share", base.share)),
            min_places=int(raw.get("min_places", base.min_places)),
            max_local=int(raw.get("max_local", base.max_local)),
        )
    except (TypeError, ValueError) as exc:
        raise CatalogError(f"{where}: {exc}") from exc


class YamlCheckCatalog:
    """Loads the check registry from the YAML files of a directory.

    Every entry is validated before the first run: its rule exists and accepts
    its parameters, its document kinds are registered. The revision is a hash
    of the files, so any change to any check gives a new revision.
    """

    def __init__(self, directory: Path, rules: RuleRegistry, kinds: DocumentKindRegistry) -> None:
        self._directory = directory
        self._rules = rules
        self._kinds = kinds

    def load(self) -> CheckCatalog:
        files = sorted(self._directory.glob("*.yaml"))
        if not files:
            raise CatalogError(f"no check catalogue in {self._directory}")
        digest = hashlib.sha256()
        families: list[CheckFamily] = []
        checks: list[CheckDefinition] = []
        for path in files:
            content = path.read_bytes()
            digest.update(path.name.encode() + b"\0" + content)
            data: dict[str, Any] = yaml.safe_load(content.decode("utf-8"))
            family = CheckFamily(code=_text(data, "family", path.name), rank=int(data["rank"]))
            families.append(family)
            checks.extend(self._entry(data, family, entry) for entry in data.get("checks", []))
        return CheckCatalog(families, checks, revision=digest.hexdigest()[:REVISION_LENGTH])

    def _entry(
        self, data: Mapping[str, Any], family: CheckFamily, entry: Mapping[str, Any]
    ) -> CheckDefinition:
        code = _text(entry, "code", family.code)
        kinds = entry.get("kinds")
        if not isinstance(kinds, list) or not kinds:
            raise CatalogError(f"{code}: kinds must be a non-empty list")
        for kind in kinds:
            try:
                self._kinds.get(kind)
            except UnknownDocumentKindError as exc:
                raise CatalogError(f"{code}: unknown document kind {kind!r}") from exc
        params = entry.get("params") or {}
        spread = _spread(
            entry.get("spread"), _spread(data.get("spread"), SpreadPolicy(), code), code
        )
        check = CheckDefinition(
            code=code,
            family=family.code,
            method=CheckMethod(_text(entry, "method", code)),
            kinds=frozenset(kinds),
            norm=_norm(data, entry, code),
            severity=Severity(_text(entry, "severity", code)),
            title=_text(entry, "title", code),
            requirement=_text(entry, "requirement", code),
            recommendation=_text(entry, "recommendation", code),
            rule=entry.get("rule"),
            params=params,
            brief=_brief(entry, code),
            spread=spread,
        )
        if check.rule is not None:
            self._rules.get(check.rule).validate(RuleParams(code, params, spread))
        return check
