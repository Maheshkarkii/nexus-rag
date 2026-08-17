import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.services.conversation import (
    create_conversation,
    create_message,
    delete_conversation,
    get_conversation_by_id,
    get_conversation_messages,
    get_conversations,
)
from app.services.query_rewriter import ConversationQueryRewriter


@pytest.mark.asyncio
async def test_conversation_crud_and_message_cascade(db_session: AsyncSession) -> None:
    # 1. Setup parent project
    project = Project(id=uuid.uuid4(), name="Conversation Project")
    db_session.add(project)
    await db_session.commit()

    # 2. Create conversation
    conv = await create_conversation(session=db_session, project_id=project.id, title="Test Chat")
    assert conv.project_id == project.id
    assert conv.title == "Test Chat"

    # 3. Retrieve
    convs = await get_conversations(session=db_session, project_id=project.id)
    assert len(convs) == 1
    assert convs[0].id == conv.id

    fetched = await get_conversation_by_id(session=db_session, conversation_id=conv.id)
    assert fetched is not None
    assert fetched.title == "Test Chat"

    # 4. Create messages
    m1 = await create_message(session=db_session, conversation_id=conv.id, role="user", content="Hi!")
    m2 = await create_message(session=db_session, conversation_id=conv.id, role="assistant", content="Hello!", metadata_json={"model": "gpt-4"})
    
    assert m1.role == "user"
    assert m1.content == "Hi!"
    assert m2.role == "assistant"
    assert m2.metadata_json == {"model": "gpt-4"}

    # 5. Fetch messages
    msgs = await get_conversation_messages(session=db_session, conversation_id=conv.id, limit=10)
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].role == "assistant"

    # 6. Delete conversation
    await delete_conversation(session=db_session, conversation=conv)
    
    # Verify cascade deletion
    fetched_deleted = await get_conversation_by_id(session=db_session, conversation_id=conv.id)
    assert fetched_deleted is None
    
    deleted_msgs = await get_conversation_messages(session=db_session, conversation_id=conv.id)
    assert len(deleted_msgs) == 0


@pytest.mark.asyncio
async def test_query_rewriter_resolves_context() -> None:
    rewriter = ConversationQueryRewriter()
    
    # Mock LLM Service returning reformulated question
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="How large was the CIFAR-10 dataset?")

    history = [
        {"role": "user", "content": "What dataset was used?"},
        {"role": "assistant", "content": "The study utilized the CIFAR-10 dataset."},
    ]

    rewritten = await rewriter.rewrite(
        messages=history,
        current_query="How large was it?",
        llm_service=mock_llm,
    )

    assert rewritten == "How large was the CIFAR-10 dataset?"
    
    # Check that LLM gets proper system/user inputs
    mock_llm.generate.assert_called_once()
    args, kwargs = mock_llm.generate.call_args
    assert "standalone research query" in kwargs["system_prompt"]
    assert "CIFAR-10" in kwargs["user_prompt"]
    assert "How large was it?" in kwargs["user_prompt"]
