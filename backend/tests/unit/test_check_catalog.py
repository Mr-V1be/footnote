"""The check registry: data in, validated definitions out."""

from __future__ import annotations

from pathlib import Path

import pytest

from snoska.bootstrap.settings import ChecksSettings
from snoska.domain.checks.catalog import CatalogError, CheckMethod, LawNorm, StandardNorm
from snoska.domain.checks.rules.registry import DEFAULT_RULES
from snoska.domain.documents.kinds import DOCUMENT_KINDS
from snoska.infrastructure.checks.catalog import YamlCheckCatalog

HEADER = "family: formatting\nrank: 1\nstandard: ГОСТ Р 7.0.97-2016\nchecks:\n"
ENTRY = """  - code: {code}
    method: deterministic
    rule: {rule}
    clause: "6.1"
    severity: advice
    kinds: [{kind}]
    title: t
    requirement: r
    recommendation: f
"""


def load(directory: Path) -> None:
    YamlCheckCatalog(directory, DEFAULT_RULES, DOCUMENT_KINDS).load()


def write(directory: Path, *entries: str) -> Path:
    (directory / "checks.yaml").write_text(HEADER + "".join(entries), encoding="utf-8")
    return directory


def test_the_shipped_catalogue_is_valid_and_grounded() -> None:
    catalog = YamlCheckCatalog(ChecksSettings().catalog_dir, DEFAULT_RULES, DOCUMENT_KINDS).load()
    for check in catalog.all():
        if check.method is CheckMethod.MODEL:
            assert isinstance(check.norm, LawNorm)
            assert check.brief is not None
        else:
            assert isinstance(check.norm, StandardNorm)
    assert catalog.applicable("pd_policy"), "a policy is checked"
    assert len(catalog.revision) == 12


def test_revision_changes_with_any_entry(tmp_path: Path) -> None:
    first = write(tmp_path, ENTRY.format(code="a", rule="date_format", kind="order"))
    before = YamlCheckCatalog(first, DEFAULT_RULES, DOCUMENT_KINDS).load().revision
    write(tmp_path, ENTRY.format(code="a", rule="date_format", kind="contract"))
    after = YamlCheckCatalog(first, DEFAULT_RULES, DOCUMENT_KINDS).load().revision
    assert before != after


@pytest.mark.parametrize(
    "entries",
    [
        (ENTRY.format(code="a", rule="no_such_rule", kind="order"),),
        (ENTRY.format(code="a", rule="date_format", kind="no_such_kind"),),
        (
            ENTRY.format(code="a", rule="date_format", kind="order"),
            ENTRY.format(code="a", rule="date_format", kind="order"),
        ),
        (ENTRY.format(code="a", rule="body_font_size", kind="order"),),
    ],
    ids=["unknown rule", "unknown kind", "duplicate code", "missing parameters"],
)
def test_an_inconsistent_catalogue_is_refused_at_load(
    tmp_path: Path, entries: tuple[str, ...]
) -> None:
    with pytest.raises(CatalogError):
        load(write(tmp_path, *entries))
