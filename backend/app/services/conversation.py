import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.conversation import Conversation
from app.db.models.message import Message

logger = logging.getLogger("ai_research_assistant.services.conversation")


async def create_conversation(
    session: AsyncSession,
    project_id: uuid.UUID,
    title: str | None = None,
) -> Conversation:
    """Create a new conversation session record linked to a project workspace."""
    db_conv = Conversation(
        project_id=project_id,
        title=title or "New Research Session",
    )
    session.add(db_conv)
    await session.commit()
    await session.refresh(db_conv)
    logger.info(f"Created conversation {db_conv.id} for project {project_id}")
    return db_conv


async def get_conversations(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> list[Conversation]:
    """Retrieve all conversations for a specific project workspace."""
    stmt = (
        select(Conversation)
        .where(Conversation.project_id == project_id)
        .order_by(Conversation.created_at.desc())
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_conversation_by_id(
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> Conversation | None:
    """Look up a conversation session record by its UUID."""
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def delete_conversation(
    session: AsyncSession,
    conversation: Conversation,
) -> None:
    """Delete a conversation session and all its cascading messages."""
    stmt = delete(Message).where(Message.conversation_id == conversation.id)
    await session.execute(stmt)
    await session.delete(conversation)
    await session.commit()
    logger.info(f"Deleted conversation {conversation.id}")


async def create_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    metadata_json: dict | None = None,
) -> Message:
    """Persist a user/assistant dialogue turn message to the database."""
    db_msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        metadata_json=metadata_json,
    )
    session.add(db_msg)
    await session.commit()
    await session.refresh(db_msg)
    logger.info(f"Persisted '{role}' message {db_msg.id} inside conversation {conversation_id}")
    return db_msg


async def get_conversation_messages(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[Message]:
    """Retrieve dialogue messages in chronological order, with limit/offset pagination support."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())
