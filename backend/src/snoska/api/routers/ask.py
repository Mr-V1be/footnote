from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from snoska.api.dependencies import ContainerDep, OrganizationAccessDep
from snoska.api.errors import PROBLEM_RESPONSES
from snoska.api.schemas.ask import (
    AskStatusOut,
    ConversationOut,
    ConversationSummaryOut,
    QuestionIn,
)

router = APIRouter(
    prefix="/v1/organizations/{organization}/ask", tags=["ask"], responses=PROBLEM_RESPONSES
)


@router.get("/status", response_model=AskStatusOut, response_model_by_alias=True)
async def ask_status(container: ContainerDep, access: OrganizationAccessDep) -> AskStatusOut:
    """Whether a model is connected to answer questions."""
    del access
    return AskStatusOut.of(await container.questions.status())


@router.get(
    "/conversations", response_model=list[ConversationSummaryOut], response_model_by_alias=True
)
async def conversations(
    container: ContainerDep, access: OrganizationAccessDep
) -> list[ConversationSummaryOut]:
    """The member's own conversations, latest first."""
    return [
        ConversationSummaryOut.of(item) for item in await container.questions.conversations(access)
    ]


@router.get(
    "/conversations/{conversation_id}", response_model=ConversationOut, response_model_by_alias=True
)
async def conversation(
    container: ContainerDep, access: OrganizationAccessDep, conversation_id: UUID
) -> ConversationOut:
    return ConversationOut.of(await container.questions.conversation(access, conversation_id))


@router.post("", response_model=ConversationOut, response_model_by_alias=True)
async def ask(
    container: ContainerDep, access: OrganizationAccessDep, body: QuestionIn
) -> ConversationOut:
    """Ask the corpus; the answer quotes the provisions it rests on, or says
    honestly that the norm does not answer."""
    view = await container.questions.ask(access, body.question, body.conversation_id)
    return ConversationOut.of(view)
