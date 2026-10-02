from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import structlog

from snoska.application.checks.engine import (
    CheckErrorCode,
    DocumentUnderCheck,
    ExecutorSession,
)
from snoska.application.checks.legal.answer import Answer, InvalidAnswer, parse_answer
from snoska.application.checks.legal.index import DocumentIndex, embed_cached
from snoska.application.checks.legal.prompt import (
    ANSWER_SCHEMA,
    Context,
    build_context,
    build_messages,
    correction,
)
from snoska.application.checks.norms import NormLibrary, ProvisionNotFoundError
from snoska.domain.checks.catalog import CheckDefinition, CheckMethod, LawNorm, ModelBrief
from snoska.domain.checks.outcome import (
    CheckOutcome,
    CitedProvision,
    Detail,
    FindingDraft,
    FindingKind,
    ResultStatus,
)
from snoska.domain.documents.structure import Block, BlockKind
from snoska.ports.ai import (
    ChatMessage,
    CompletionRequest,
    Embedder,
    LanguageModel,
    MessageRole,
    ModelOutputError,
)

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class LegalCheckSettings:
    """How model checks run. Concurrency should match what the model server
    serves in parallel; more only queues requests on its side."""

    concurrency: int = 2
    fragments: int = 8
    related_norms: int = 1
    max_attempts: int = 3
    max_tokens: int = 450
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
    recommendation = answer.recommendation or None
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
    def __init__(
        self,
        executor: LegalExecutor,
        document: DocumentUnderCheck,
        index: DocumentIndex,
        queries: Mapping[str, Sequence[float]],
    ) -> None:
        self.concurrency = executor.settings.concurrency
        self._executor = executor
        self._document = document
        self._index = index
        self._queries = queries
        self._blocks = {block.ordinal: block for block in document.structure.blocks}
        self._outline = _outline(document.structure.blocks)

    async def execute(self, check: CheckDefinition) -> CheckOutcome:
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
        context = build_context([*named, *related], fragments)
        return await self._ask(brief, context)

    async def _ask(self, brief: ModelBrief, context: Context) -> CheckOutcome:
        settings = self._executor.settings
        messages = build_messages(brief, context, self._document.title, self._outline)
        for attempt in range(1, settings.max_attempts + 1):
            completion_text = ""
            try:
                completion = await self._executor.model.complete(
                    CompletionRequest(
                        messages=messages,
                        response_schema=ANSWER_SCHEMA,
                        temperature=0.0,
                        max_tokens=settings.max_tokens,
                        options=settings.model_options,
                    )
                )
                completion_text = completion.text
                answer = parse_answer(completion_text, context, self._blocks)
            except (InvalidAnswer, ModelOutputError) as exc:
                problem = exc.problem if isinstance(exc, InvalidAnswer) else "ответ не JSON."
                log.info("checks.answer_rejected", attempt=attempt, problem=problem)
                messages = (
                    *messages,
                    ChatMessage(MessageRole.ASSISTANT, completion_text or "{}"),
                    correction(problem),
                )
                continue
            return outcome_of(answer, context, attempt)
        return CheckOutcome.failed(CheckErrorCode.INVALID_MODEL_ANSWER, settings.max_attempts)


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
    ) -> ExecutorSession:
        index = await DocumentIndex.build(document.structure, self.embedder, document.embeddings)
        searches = sorted({check.brief.search for check in checks if check.brief is not None})
        queries = await embed_cached(searches, self.embedder, document.embeddings)
        return _LegalSession(self, document, index, queries)
