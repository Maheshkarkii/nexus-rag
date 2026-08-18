import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.project import Project


@pytest.mark.asyncio
async def test_conversations_api_lifecycle(
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    # 1. Setup project
    project = Project(id=uuid.uuid4(), name="API Chat Project")
    db_session.add(project)
    await db_session.commit()

    # 2. POST /projects/{project_id}/conversations (Create)
    payload = {"title": "Lifecycle Chat"}
    response = await async_client.post(
        f"/api/v1/projects/{project.id}/conversations",
        json=payload,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == "Lifecycle Chat"
    conv_id = data["id"]

    # 3. GET /projects/{project_id}/conversations (List)
    response = await async_client.get(f"/api/v1/projects/{project.id}/conversations")
    assert response.status_code == status.HTTP_200_OK
    convs = response.json()
    assert len(convs) == 1
    assert convs[0]["id"] == conv_id

    # 4. GET /conversations/{conversation_id}/messages (Get History - empty initially)
    response = await async_client.get(f"/api/v1/conversations/{conv_id}/messages")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []

    # Insert messages manually in database
    m1 = Message(conversation_id=uuid.UUID(conv_id), role="user", content="Hi assistant!")
    db_session.add(m1)
    await db_session.commit()

    # Get History again
    response = await async_client.get(f"/api/v1/conversations/{conv_id}/messages?limit=5")
    assert response.status_code == status.HTTP_200_OK
    msgs = response.json()
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Hi assistant!"

    # 5. DELETE /conversations/{conversation_id} (Delete)
    response = await async_client.delete(f"/api/v1/conversations/{conv_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify deleted
    response = await async_client.get(f"/api/v1/conversations/{conv_id}/messages")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_conversations_project_isolation_violations(
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    p1 = Project(id=uuid.uuid4(), name="Project 1")
    p2 = Project(id=uuid.uuid4(), name="Project 2")
    db_session.add_all([p1, p2])
    await db_session.commit()

    # Create conversation in Project 1
    c1 = Conversation(id=uuid.uuid4(), project_id=p1.id, title="P1 Session")
    db_session.add(c1)
    await db_session.commit()

    # Try listing conversations of non-existent project
    response = await async_client.get(f"/api/v1/projects/{uuid.uuid4()}/conversations")
    assert response.status_code == status.HTTP_404_NOT_FOUND

    # Try creating conversation inside non-existent project
    response = await async_client.post(f"/api/v1/projects/{uuid.uuid4()}/conversations", json={"title": "Test"})
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
@patch("app.services.retrieval.QdrantService")
@patch("sentence_transformers.CrossEncoder")
@patch("app.services.llm.AsyncOpenAI")
async def test_ask_endpoint_with_conversation(
    mock_openai_class: MagicMock,
    mock_cross_encoder_class: MagicMock,
    mock_qdrant_class: MagicMock,
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    p = Project(id=uuid.uuid4(), name="RAG Chat Project")
    db_session.add(p)
    await db_session.commit()

    c = Conversation(id=uuid.uuid4(), project_id=p.id, title="RAG Session")
    db_session.add(c)
    await db_session.commit()

    # Mock Qdrant
    mock_qdrant = MagicMock()
    mock_qdrant.health_check.return_value = True
    mock_qdrant_class.return_value = mock_qdrant

    mock_hit = MagicMock()
    mock_hit.score = 0.95
    mock_hit.payload = {
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "project_id": str(p.id),
        "chunk_index": 0,
        "text": "The project uses Adam optimizer.",
        "source_filename": "info.pdf",
    }
    mock_qclient = MagicMock()
    mock_qresponse = MagicMock()
    mock_qresponse.points = [mock_hit]
    mock_qclient.query_points.return_value = mock_qresponse
    mock_qclient.search.return_value = [mock_hit]
    mock_qdrant.connect.return_value = mock_qclient

    # Mock Reranker
    from app.services.reranking import default_reranking_service
    default_reranking_service._model = None
    mock_rerank_instance = MagicMock()
    mock_cross_encoder_class.return_value = mock_rerank_instance
    mock_rerank_instance.predict.return_value = [4.0]

    # Mock LLM completions response
    from app.services.llm import default_llm_service
    default_llm_service.api_key = "mock-key"
    default_llm_service._client = None
    
    mock_openai = MagicMock()
    mock_openai_class.return_value = mock_openai
    
    mock_choice = MagicMock()
    mock_choice.message.content = "Adam was chosen [S1]."
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_completion)

    from app.main import app
    from app.services.qdrant import get_qdrant_service
    app.dependency_overrides[get_qdrant_service] = lambda: mock_qdrant

    try:
        # First turn: ask question
        payload = {
            "query": "What optimizer was used?",
            "conversation_id": str(c.id),
        }

        response = await async_client.post(
            f"/api/v1/projects/{p.id}/ask",
            json=payload,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "Adam" in data["answer"]
        assert data["conversation_id"] == str(c.id)

        # Check messages persisted
        response_history = await async_client.get(f"/api/v1/conversations/{c.id}/messages")
        assert response_history.status_code == status.HTTP_200_OK
        msgs = response_history.json()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "What optimizer was used?"
        assert msgs[1]["role"] == "assistant"
        assert "Adam" in msgs[1]["content"]

    finally:
        app.dependency_overrides.clear()
        default_llm_service.api_key = None
