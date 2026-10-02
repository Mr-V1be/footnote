from __future__ import annotations

from collections.abc import Iterable

from snoska.domain.checks.catalog import CatalogError
from snoska.domain.checks.rules.base import Rule
from snoska.domain.checks.rules.dates import DateFormatRule
from snoska.domain.checks.rules.layout import PageMarginsRule
from snoska.domain.checks.rules.numbering import ArabicNumberingRule, NumberingSequenceRule
from snoska.domain.checks.rules.requisites import RequisitePresentRule, SignatureOrderRule
from snoska.domain.checks.rules.typography import (
    BodyFontSizeRule,
    LineSpacingRule,
    ParagraphIndentRule,
)


class RuleRegistry:
    """Deterministic rules by id. A catalogue entry names its rule here."""

    def __init__(self, rules: Iterable[Rule]) -> None:
        self._rules: dict[str, Rule] = {}
        for rule in rules:
            if rule.id in self._rules:
                raise CatalogError(f"duplicate rule id {rule.id!r}")
            self._rules[rule.id] = rule

    def get(self, rule_id: str) -> Rule:
        try:
            return self._rules[rule_id]
        except KeyError as exc:
            raise CatalogError(f"unknown rule {rule_id!r}") from exc


DEFAULT_RULES = RuleRegistry(
    [
        PageMarginsRule(),
        BodyFontSizeRule(),
        LineSpacingRule(),
        ParagraphIndentRule(),
        RequisitePresentRule(),
        SignatureOrderRule(),
        ArabicNumberingRule(),
        NumberingSequenceRule(),
        DateFormatRule(),
    ]
)
