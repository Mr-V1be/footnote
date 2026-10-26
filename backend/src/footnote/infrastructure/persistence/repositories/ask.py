from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from footnote.domain.ask.answer import Answer, AnswerStatus, Citation, Conversation, Turn
from footnote.domain.shared.locale import LocalizedText
from footnote.infrastructure.persistence.tables.ask import conversation_turns, conversations


def _conversation(row: RowMapping) -> Conversation:
    return Conversation(
        id=row["id"],
        organization_id=row["organization_id"],
        user_id=row["user_id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _turn(row: RowMapping) -> Turn:
    return Turn(
        id=row["id"],
        conversation_id=row["conversation_id"],
        ordinal=row["ordinal"],
        question=row["question"],
        answer=Answer(
            status=AnswerStatus(row["status"]),
            text=row["answer"],
            citations=tuple(
                Citation(
                    number=item["number"],
                    act_code=item["act"],
                    edition_id=UUID(item["edition"]),
                    anchor=item["anchor"],
                    citation=LocalizedText.from_mapping(item["citation"]),
                    quote=item["quote"],
                )
                for item in row["citations"]
            ),
        ),
        model=row["model"],
        asked_at=row["asked_at"],
    )


class SqlConversationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def list_for_user(self, user_id: UUID, *, limit: int) -> Sequence[Conversation]:
        result = await self._connection.execute(
            select(conversations)
            .where(conversations.c.user_id == user_id)
            .order_by(conversations.c.updated_at.desc())
            .limit(limit)
        )
        return [_conversation(row) for row in result.mappings()]

    async def get(self, conversation_id: UUID) -> Conversation | None:
        row = (
            (
                await self._connection.execute(
                    select(conversations).where(conversations.c.id == conversation_id)
                )
            )
            .mappings()
            .first()
        )
        return _conversation(row) if row else None

    async def add(self, conversation: Conversation) -> None:
        await self._connection.execute(
            insert(conversations).values(
                id=conversation.id,
                organization_id=conversation.organization_id,
                user_id=conversation.user_id,
                title=conversation.title,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            )
        )

    async def touch(self, conversation_id: UUID, now: datetime) -> None:
        await self._connection.execute(
            update(conversations)
            .where(conversations.c.id == conversation_id)
            .values(updated_at=now)
        )

    async def add_turn(self, turn: Turn) -> None:
        conversation = await self.get(turn.conversation_id)
        if conversation is None:
            raise RuntimeError("the conversation does not exist")
        await self._connection.execute(
            insert(conversation_turns).values(
                id=turn.id,
                organization_id=conversation.organization_id,
                conversation_id=turn.conversation_id,
                ordinal=turn.ordinal,
                question=turn.question,
                status=turn.answer.status.value,
                answer=turn.answer.text,
                citations=[
                    {
                        "number": citation.number,
                        "act": citation.act_code,
                        "edition": str(citation.edition_id),
                        "anchor": citation.anchor,
                        "citation": citation.citation.as_mapping(),
                        "quote": citation.quote,
                    }
                    for citation in turn.answer.citations
                ],
                model=turn.model,
                asked_at=turn.asked_at,
            )
        )

    async def turns(self, conversation_id: UUID) -> Sequence[Turn]:
        result = await self._connection.execute(
            select(conversation_turns)
            .where(conversation_turns.c.conversation_id == conversation_id)
            .order_by(conversation_turns.c.ordinal)
        )
        return [_turn(row) for row in result.mappings()]
