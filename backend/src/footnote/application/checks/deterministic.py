from __future__ import annotations

from collections.abc import Sequence

from footnote.application.checks.engine import DocumentUnderCheck, ExecutorSession
from footnote.domain.checks.catalog import CheckDefinition, CheckMethod
from footnote.domain.checks.outcome import CheckOutcome
from footnote.domain.checks.rules.base import RuleParams
from footnote.domain.checks.rules.registry import RuleRegistry


class _RuleSession:
    # Rules are pure and quick: running them one after another is fastest.
    concurrency = 1

    def __init__(self, rules: RuleRegistry, document: DocumentUnderCheck) -> None:
        self._rules = rules
        self._document = document

    async def execute(self, check: CheckDefinition) -> CheckOutcome:
        rule = self._rules.get(check.rule or "")
        return rule.evaluate(
            self._document.structure, RuleParams(check.code, check.params, check.spread)
        )


class DeterministicExecutor:
    """Formatting checks: rules of the registry over the parsed structure."""

    method = CheckMethod.DETERMINISTIC

    def __init__(self, rules: RuleRegistry) -> None:
        self._rules = rules

    async def open(
        self, document: DocumentUnderCheck, checks: Sequence[CheckDefinition]
    ) -> ExecutorSession:
        return _RuleSession(self._rules, document)
