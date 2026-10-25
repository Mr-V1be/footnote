from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field

import structlog

from snoska.application.checks.engine import (
    BatchSession,
    CheckErrorCode,
    DocumentUnderCheck,
)
from snoska.application.checks.legal.answer import Answer, parse_batch
from snoska.application.checks.legal.index import DocumentIndex, embed_cached
from snoska.application.checks.legal.prompt import (
    BATCH_SCHEMA,
    Context,
    PreparedCheck,
    answer_tokens,
    build_batch_context,
    build_messages,
)
from snoska.application.checks.norms import NormLibrary, ProvisionNotFoundError
from snoska.domain.checks.catalog import CheckDefinition, CheckMethod, LawNorm
from snoska.domain.checks.outcome import (
    CheckOutcome,
    CitedProvision,
    Detail,
    FindingDraft,
    FindingKind,
    ResultStatus,
)
from snoska.domain.documents.structure import Block, BlockKind
from snoska.ports.ai import CompletionRequest, Embedder, LanguageModel, ModelOutputError

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class LegalCheckSettings:
    """How model checks run. Requirements of a document go to the model
    together, ``checks_per_request`` at a time; a rejected verdict is asked
    again, alone with the other rejected ones, up to ``max_attempts``."""

    checks_per_request: int = 12
    fragments: int = 4
    related_norms: int = 1
    max_attempts: int = 2
    model_options: Mapping[str, object] = field(default_factory=dict)


def _outline(blocks: Sequence[Block]) -> list[str]:
    return [
        " ".join(part for part in (block.label, block.text) if part)
        for block in blocks
        if block.kind is BlockKind.HEADING
    ]


def _cited(context: Context, answer: Answer) -> CitedProvision:
    provision = context.norms[answer.norm_key]
    return CitedProvision(
        act_code=provision.act_code,
        edition_id=provision.edition_id,
        anchor=provision.anchor,
        citation=provision.citation,
    )


def outcome_of(answer: Answer, context: Context, attempts: int) -> CheckOutcome:
    """Turn a grounded answer into a verdict with findings."""
    cited = _cited(context, answer)
    first = answer.quotes[0] if answer.quotes else None
    recommendation = answer.recommendation
    detail = Detail.written(answer.explanation)
    match answer.verdict:
        case "present":
            return CheckOutcome(
                ResultStatus.PASSED, evidence=answer.quotes, cited=cited, attempts=attempts
            )
        case "uncertain":
            finding = FindingDraft(FindingKind.REVIEW, detail, location=first)
            return CheckOutcome(
                ResultStatus.NEEDS_REVIEW, findings=(finding,), cited=cited, attempts=attempts
            )
        case _:
            # "partial" points at what is there; "absent" concerns the whole document.
            finding = FindingDraft(
                FindingKind.VIOLATION, detail, location=first, recommendation=recommendation
            )
            return CheckOutcome(
                ResultStatus.VIOLATION, findings=(finding,), cited=cited, attempts=attempts
            )


class _LegalSession:
    """The model checks of one document, asked in batches."""

    def __init__(
        self,
        executor: LegalExecutor,
        document: DocumentUnderCheck,
        index: DocumentIndex,
        queries: Mapping[str, Sequence[float]],
    ) -> None:
        self._executor = executor
        self._document = document
        self._index = index
        self._queries = queries
        self._blocks = {block.ordinal: block for block in document.structure.blocks}
        self._outline = _outline(document.structure.blocks)

    async def execute_many(
        self, checks: Sequence[CheckDefinition]
    ) -> AsyncIterator[tuple[CheckDefinition, CheckOutcome]]:
        prepared: list[PreparedCheck] = []
        for check in checks:
            ready = await self._prepare(check)
            if isinstance(ready, CheckOutcome):
                yield check, ready
            else:
                prepared.append(ready)
        size = max(1, self._executor.settings.checks_per_request)
        for start in range(0, len(prepared), size):
            async for settled in self._ask(prepared[start : start + size]):
                yield settled

    async def _prepare(self, check: CheckDefinition) -> PreparedCheck | CheckOutcome:
        brief, norm = check.brief, check.norm
        if brief is None or not isinstance(norm, LawNorm):
            raise ValueError(f"{check.code} is not a model check")
        settings = self._executor.settings
        query = self._queries[brief.search]
        try:
            named = await self._executor.norms.provisions(norm)
        except ProvisionNotFoundError:
            log.warning("checks.norm_unavailable", check=check.code)
            return CheckOutcome.failed(CheckErrorCode.NORM_UNAVAILABLE)
        related = await self._executor.norms.related(
            norm.act_code,
            self._executor.embedder.space,
            query,
            exclude=set(norm.anchors),
            limit=settings.related_norms,
        )
        fragments = self._index.search(query, brief.keywords, settings.fragments)
        if not fragments:
            return CheckOutcome.not_applicable()
        return PreparedCheck(check, brief, (*named, *related), tuple(fragments))

    async def _ask(
        self, batch: Sequence[PreparedCheck]
    ) -> AsyncIterator[tuple[CheckDefinition, CheckOutcome]]:
        settings = self._executor.settings
        remaining = list(batch)
        problems: dict[str, str] = {}
        for attempt in range(1, settings.max_attempts + 1):
            if not remaining:
                return
            context = build_batch_context(remaining)
            earlier = {
                key: problems[item.check.code]
                for key, item in context.checks.items()
                if item.check.code in problems
            }
            request = CompletionRequest(
                messages=build_messages(context, self._outline, earlier),
                response_schema=BATCH_SCHEMA,
                temperature=0.0,
                max_tokens=answer_tokens(len(remaining)),
                options=settings.model_options,
            )
            try:
                text = (await self._executor.model.complete(request)).text
            except ModelOutputError:
                text = ""
            parsed = parse_batch(text, context, self._blocks)
            problems = {}
            for key, item in context.checks.items():
                answer = parsed.answers.get(key)
                if answer is not None:
                    yield item.check, outcome_of(answer, context.context_of(key), attempt)
                else:
                    problems[item.check.code] = parsed.problems[key]
            if problems:
                log.info("checks.verdicts_rejected", attempt=attempt, problems=problems)
            remaining = [item for item in remaining if item.check.code in problems]
        for item in remaining:
            yield (
                item.check,
                CheckOutcome.failed(CheckErrorCode.INVALID_MODEL_ANSWER, settings.max_attempts),
            )


class LegalExecutor:
    """152-FZ checks: the language model reads the passages of the document
    retrieved for a requirement next to the provisions it rests on."""

    method = CheckMethod.MODEL

    def __init__(
        self,
        embedder: Embedder,
        model: LanguageModel,
        norms: NormLibrary,
        settings: LegalCheckSettings,
    ) -> None:
        self.embedder = embedder
        self.model = model
        self.norms = norms
        self.settings = settings

    async def open(
        self, document: DocumentUnderCheck, checks: Sequence[CheckDefinition]
    ) -> BatchSession:
        index = await DocumentIndex.build(document.structure, self.embedder, document.embeddings)
        searches = sorted({check.brief.search for check in checks if check.brief is not None})
        queries = await embed_cached(searches, self.embedder, document.embeddings)
        return _LegalSession(self, document, index, queries)
