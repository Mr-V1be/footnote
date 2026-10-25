from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import structlog

from snoska.application.ask.prompt import ANSWER_SCHEMA, build_messages, correction
from snoska.application.billing.meter import Charge, UsageMeter
from snoska.application.checks.norms import NormLibrary, Provision
from snoska.application.corpus.search import CorpusNotIndexedError
from snoska.domain.ask.answer import (
    QUESTION_MAX_LENGTH,
    Answer,
    Conversation,
    SourceProvision,
    Turn,
    UngroundedAnswerError,
    read_answer,
    title_of,
)
from snoska.domain.billing.plans import UsageMetric
from snoska.domain.billing.usage import LedgerReason, ensure_allowance
from snoska.domain.checks.catalog import LawNorm
from snoska.domain.shared.errors import NotFoundError, ValidationError
from snoska.domain.shared.ids import new_id
from snoska.domain.shared.locale import Locale
from snoska.domain.tenancy.access import OrganizationAccess
from snoska.domain.tenancy.permissions import Permission
from snoska.ports.ai import (
    ChatMessage,
    CompletionRequest,
    Embedder,
    LanguageModel,
    MessageRole,
    ModelOutputError,
    RequestBudget,
)
from snoska.ports.clock import Clock
from snoska.ports.unit_of_work import UnitOfWorkFactory

log = structlog.get_logger(__name__)

PROVISIONS = 8
MAX_ATTEMPTS = 3
MAX_TOKENS = 700
CONVERSATIONS_LISTED = 30


class ConversationNotFoundError(NotFoundError):
    code = "conversation_not_found"


class EmptyQuestionError(ValidationError):
    code = "empty_question"


class InvalidAnswerError(ValidationError):
    """The model gave no grounded answer after the allowed attempts."""

    code = "invalid_model_answer"


@dataclass(frozen=True, slots=True)
class AskStatus:
    """Whether questions can be answered here, and with which models."""

    configured: bool
    language_model: str | None
    embedding_model: str | None
    # Model requests left today on a free tier; None without a daily allowance.
    requests_left_today: int | None = None


@dataclass(frozen=True, slots=True)
class RecordedCitation:
    """A footnote of a recorded answer: the provision by its anchor and the
    words quoted from it."""

    anchor: str
    quote: str


@dataclass(frozen=True, slots=True)
class RecordedAnswer:
    """An answer given earlier, kept as data (the demo stand's questions):
    shown without a request to the model, checked like a live answer."""

    question: str
    text: str
    citations: tuple[RecordedCitation, ...]
    model: str
    act_code: str = "152-fz"
    # When it was asked; now when not given.
    asked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ConversationView:
    conversation: Conversation
    turns: Sequence[Turn]


class NormQuestions:
    """«Спросить норму»: answers from the corpus with quotes, or an honest
    "not found in the norm". Answers are grounded like legal checks: every
    footnote quotes a provision that was shown to the model, word for word."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        norms: NormLibrary,
        embedder: Embedder,
        model: LanguageModel,
        meter: UsageMeter,
        clock: Clock,
        *,
        configured: bool,
        budget: RequestBudget | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._norms = norms
        self._embedder = embedder
        self._model = model
        self._meter = meter
        self._clock = clock
        self._configured = configured
        self._budget = budget

    async def status(self) -> AskStatus:
        return AskStatus(
            configured=self._configured,
            language_model=self._model.model or None,
            embedding_model=self._embedder.model or None,
            requests_left_today=await self._budget.remaining_today() if self._budget else None,
        )

    async def conversations(self, access: OrganizationAccess) -> Sequence[Conversation]:
        access.require(Permission.NORMS_ASK)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            return await uow.conversations.list_for_user(access.user_id, limit=CONVERSATIONS_LISTED)

    async def conversation(
        self, access: OrganizationAccess, conversation_id: UUID
    ) -> ConversationView:
        access.require(Permission.NORMS_ASK)
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            conversation = await uow.conversations.get(conversation_id)
            if conversation is None or conversation.user_id != access.user_id:
                raise ConversationNotFoundError("conversation not found")
            turns = await uow.conversations.turns(conversation_id)
        return ConversationView(conversation=conversation, turns=turns)

    async def ask(
        self,
        access: OrganizationAccess,
        question: str,
        conversation_id: UUID | None,
        locale: Locale,
    ) -> ConversationView:
        """Answer in the asker's language, with quotes in the law's own words."""
        access.require(Permission.NORMS_ASK)
        text = " ".join(question.split())[:QUESTION_MAX_LENGTH]
        if not text:
            raise EmptyQuestionError("the question is empty")
        earlier: Sequence[Turn] = []
        if conversation_id is not None:
            earlier = (await self.conversation(access, conversation_id)).turns
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            subscription = await self._meter.subscription(uow, access.organization_id, lock=False)
            used = await uow.ledger.totals(subscription.period_start)
            await uow.commit()
        ensure_allowance(
            self._meter.plan_of(subscription),
            UsageMetric.QUESTIONS,
            used.get(UsageMetric.QUESTIONS, 0),
            1,
        )
        answer = await self._answer(text, earlier, locale)
        return await self._store(access, text, answer, conversation_id, len(earlier))

    async def record(self, access: OrganizationAccess, recorded: RecordedAnswer) -> Conversation:
        """Store a recorded answer as the person's conversation, unless they
        already have one with that question. The quotes are checked against
        the edition in force, as a live answer's are."""
        access.require(Permission.NORMS_ASK)
        question = " ".join(recorded.question.split())
        for conversation in await self.conversations(access):
            if conversation.title == title_of(question):
                return conversation
        anchors = tuple(dict.fromkeys(item.anchor for item in recorded.citations))
        provisions = await self._norms.provisions(LawNorm(recorded.act_code, anchors))
        sources = _sources(provisions)
        key_of = {source.anchor: source.key for source in sources}
        raw = json.dumps(
            {
                "found": True,
                "answer": recorded.text,
                "citations": [
                    {"norm": key_of[item.anchor], "quote": item.quote}
                    for item in recorded.citations
                ],
            },
            ensure_ascii=False,
        )
        answer = read_answer(raw, sources)
        view = await self._store(
            access, question, answer, None, 0, model=recorded.model, at=recorded.asked_at
        )
        return view.conversation

    async def _answer(self, question: str, earlier: Sequence[Turn], locale: Locale) -> Answer:
        space = self._embedder.space
        async with self._uow_factory.for_platform() as uow:
            indexed = await uow.corpus.indexed_active_editions(space, None)
        if not indexed:
            raise CorpusNotIndexedError(f"no edition in force is indexed in space {space.code!r}")
        [vector] = await self._embedder.embed([question])
        provisions = await self._norms.nearest(self._embedder.space, vector, PROVISIONS)
        sources = _sources(provisions)
        messages: tuple[ChatMessage, ...] = build_messages(question, sources, earlier, locale)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            raw = ""
            try:
                completion = await self._model.complete(
                    CompletionRequest(
                        messages=messages,
                        response_schema=ANSWER_SCHEMA,
                        temperature=0.0,
                        max_tokens=MAX_TOKENS,
                    )
                )
                raw = completion.text
                return read_answer(raw, sources)
            except (UngroundedAnswerError, ModelOutputError) as exc:
                problem = (
                    exc.problem if isinstance(exc, UngroundedAnswerError) else "ответ не JSON."
                )
                log.info("ask.answer_rejected", attempt=attempt, problem=problem)
                messages = (
                    *messages,
                    ChatMessage(MessageRole.ASSISTANT, raw or "{}"),
                    correction(problem),
                )
        raise InvalidAnswerError("the model gave no grounded answer")

    async def _store(
        self,
        access: OrganizationAccess,
        question: str,
        answer: Answer,
        conversation_id: UUID | None,
        ordinal: int,
        *,
        model: str | None = None,
        at: datetime | None = None,
    ) -> ConversationView:
        now = at or self._clock.now()
        async with self._uow_factory.for_tenant(access.organization_id) as uow:
            if conversation_id is None:
                conversation = Conversation(
                    id=new_id(),
                    organization_id=access.organization_id,
                    user_id=access.user_id,
                    title=title_of(question),
                    created_at=now,
                    updated_at=now,
                )
                await uow.conversations.add(conversation)
            else:
                found = await uow.conversations.get(conversation_id)
                if found is None:
                    raise ConversationNotFoundError("conversation not found")
                conversation = found
                await uow.conversations.touch(conversation.id, now)
            turn = Turn(
                id=new_id(),
                conversation_id=conversation.id,
                ordinal=ordinal,
                question=question,
                answer=answer,
                model=model or self._model.model,
                asked_at=now,
            )
            await self._meter.consume(
                uow,
                access.organization_id,
                (Charge(UsageMetric.QUESTIONS, 1),),
                LedgerReason.QUESTION,
                reference=str(turn.id),
            )
            await uow.conversations.add_turn(turn)
            turns = await uow.conversations.turns(conversation.id)
            await uow.commit()
        return ConversationView(conversation=conversation, turns=turns)


def _sources(provisions: Sequence[Provision]) -> list[SourceProvision]:
    """Provisions under the keys an answer cites them by (N1, N2…)."""
    return [
        SourceProvision(
            key=f"N{index}",
            act_code=provision.act_code,
            edition_id=provision.edition_id,
            anchor=provision.anchor,
            citation=provision.citation,
            text=provision.text,
        )
        for index, provision in enumerate(provisions, start=1)
    ]
