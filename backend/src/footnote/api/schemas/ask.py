from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from footnote.api.schemas.common import ApiModel
from footnote.application.ask.service import AskStatus, ConversationView
from footnote.domain.ask.answer import AnswerStatus, Citation, Conversation, Turn
from footnote.domain.shared.locale import Locale


class AskStatusOut(ApiModel):
    configured: bool
    language_model: str | None
    embedding_model: str | None
    requests_left_today: int | None

    @classmethod
    def of(cls, status: AskStatus) -> AskStatusOut:
        return cls(
            configured=status.configured,
            language_model=status.language_model,
            embedding_model=status.embedding_model,
            requests_left_today=status.requests_left_today,
        )


class CitationOut(ApiModel):
    """A footnote: the provision cited in the language of the request, and
    its words as the law has them."""

    number: int
    act_code: str
    anchor: str
    citation: str
    quote: str

    @classmethod
    def of(cls, citation: Citation, locale: Locale) -> CitationOut:
        return cls(
            number=citation.number,
            act_code=citation.act_code,
            anchor=citation.anchor,
            citation=citation.citation.resolve(locale),
            quote=citation.quote,
        )


class TurnOut(ApiModel):
    id: UUID
    question: str
    status: AnswerStatus
    # With footnote markers [1], [2]… pointing at ``citations``.
    answer: str | None
    citations: list[CitationOut]
    asked_at: datetime

    @classmethod
    def of(cls, turn: Turn, locale: Locale) -> TurnOut:
        return cls(
            id=turn.id,
            question=turn.question,
            status=turn.answer.status,
            answer=turn.answer.text,
            citations=[CitationOut.of(item, locale) for item in turn.answer.citations],
            asked_at=turn.asked_at,
        )


class ConversationSummaryOut(ApiModel):
    id: UUID
    title: str
    updated_at: datetime

    @classmethod
    def of(cls, conversation: Conversation) -> ConversationSummaryOut:
        return cls(id=conversation.id, title=conversation.title, updated_at=conversation.updated_at)


class ConversationOut(ApiModel):
    id: UUID
    title: str
    turns: list[TurnOut]

    @classmethod
    def of(cls, view: ConversationView, locale: Locale) -> ConversationOut:
        return cls(
            id=view.conversation.id,
            title=view.conversation.title,
            turns=[TurnOut.of(turn, locale) for turn in view.turns],
        )


class QuestionIn(ApiModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: UUID | None = None
