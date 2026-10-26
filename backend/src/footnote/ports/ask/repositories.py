from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from footnote.domain.ask.answer import Conversation, Turn


class ConversationRepository(Protocol):
    """Tenant-scoped; a member sees their own conversations."""

    async def list_for_user(self, user_id: UUID, *, limit: int) -> Sequence[Conversation]: ...

    async def get(self, conversation_id: UUID) -> Conversation | None: ...

    async def add(self, conversation: Conversation) -> None: ...

    async def touch(self, conversation_id: UUID, now: datetime) -> None: ...

    async def add_turn(self, turn: Turn) -> None: ...

    async def turns(self, conversation_id: UUID) -> Sequence[Turn]: ...
