from __future__ import annotations

from collections.abc import Sequence

from snoska.application.checks.engine import DocumentUnderCheck, ExecutorSession
from snoska.domain.checks.catalog import CheckDefinition, CheckMethod
from snoska.domain.checks.outcome import CheckOutcome
from snoska.domain.checks.rules.base import RuleParams
from snoska.domain.checks.rules.registry import RuleRegistry


class _RuleSession:
    # Rules are pure and quick: running them one after another is fastest.
    concurrency = 1

    def __init__(self, rules: RuleRegistry, document: DocumentUnderCheck) -> None:
        self._rules = rules
        self._document = document

    async def execute(self, check: CheckDefinition) -> CheckOutcome:
        rule = self._rules.get(check.rule or "")
        return rule.evaluate(self._document.structure, RuleParams(check.code, check.params))


class DeterministicExecutor:
    """Formatting checks: rules of the registry over the parsed structure."""

    method = CheckMethod.DETERMINISTIC

    def __init__(self, rules: RuleRegistry) -> None:
        self._rules = rules

    async def open(
        self, document: DocumentUnderCheck, checks: Sequence[CheckDefinition]
    ) -> ExecutorSession:
        return _RuleSession(self._rules, document)
