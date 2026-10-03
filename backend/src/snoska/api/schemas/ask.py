from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from snoska.api.schemas.common import ApiModel
from snoska.application.ask.service import AskStatus, ConversationView
from snoska.domain.ask.answer import AnswerStatus, Citation, Conversation, Turn


class AskStatusOut(ApiModel):
    configured: bool
    language_model: str | None
    embedding_model: str | None

    @classmethod
    def of(cls, status: AskStatus) -> AskStatusOut:
        return cls(
            configured=status.configured,
            language_model=status.language_model,
            embedding_model=status.embedding_model,
        )


class CitationOut(ApiModel):
    number: int
    act_code: str
    anchor: str
    citation: str
    quote: str

    @classmethod
    def of(cls, citation: Citation) -> CitationOut:
        return cls(
            number=citation.number,
            act_code=citation.act_code,
            anchor=citation.anchor,
            citation=citation.citation,
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
    def of(cls, turn: Turn) -> TurnOut:
        return cls(
            id=turn.id,
            question=turn.question,
            status=turn.answer.status,
            answer=turn.answer.text,
            citations=[CitationOut.of(item) for item in turn.answer.citations],
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
    def of(cls, view: ConversationView) -> ConversationOut:
        return cls(
            id=view.conversation.id,
            title=view.conversation.title,
            turns=[TurnOut.of(turn) for turn in view.turns],
        )


class QuestionIn(ApiModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: UUID | None = None
