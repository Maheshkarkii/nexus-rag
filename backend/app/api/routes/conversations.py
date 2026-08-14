import logging
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    MessageResponse,
)
from app.services.conversation import (
    create_conversation,
    delete_conversation,
    get_conversation_by_id,
    get_conversation_messages,
    get_conversations,
)
from app.services.project import get_project_by_id

logger = logging.getLogger("ai_research_assistant.api.routes.conversations")

router = APIRouter()


@router.post(
    "/projects/{project_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Research Session",
    description="Create a new conversation or research session within a project workspace.",
)
async def create_new_session(
    project_id: uuid.UUID,
    payload: ConversationCreate,
    session: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Create a new research conversation workspace."""
    project = await get_project_by_id(session=session, project_id=project_id)
    if not project:
        raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")

    db_conv = await create_conversation(
        session=session,
        project_id=project_id,
        title=payload.title,
    )
    return ConversationResponse.model_validate(db_conv)


@router.get(
    "/projects/{project_id}/conversations",
    response_model=list[ConversationResponse],
    status_code=status.HTTP_200_OK,
    summary="List Research Sessions",
    description="Retrieve lightweight metadata for all conversation sessions within a project workspace.",
)
async def list_project_sessions(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ConversationResponse]:
    """List conversations in a project."""
    project = await get_project_by_id(session=session, project_id=project_id)
    if not project:
        raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")

    db_convs = await get_conversations(session=session, project_id=project_id)
    return [ConversationResponse.model_validate(c) for c in db_convs]


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Message History",
    description="Retrieve chronologically ordered dialogue history messages for a conversation session.",
)
async def get_session_history(
    conversation_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    session: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
    """Retrieve paginated conversation messages."""
    conv = await get_conversation_by_id(session=session, conversation_id=conversation_id)
    if not conv:
        raise NotFoundException(message=f"Conversation with ID '{conversation_id}' was not found.")

    db_msgs = await get_conversation_messages(
        session=session,
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )
    return [MessageResponse.model_validate(m) for m in db_msgs]


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Research Session",
    description="Permanently delete a conversation session and all its associated messages.",
)
async def remove_session(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a conversation."""
    conv = await get_conversation_by_id(session=session, conversation_id=conversation_id)
    if not conv:
        raise NotFoundException(message=f"Conversation with ID '{conversation_id}' was not found.")

    await delete_conversation(session=session, conversation=conv)
    return None
