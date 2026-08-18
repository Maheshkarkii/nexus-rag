import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project


@pytest.mark.asyncio
@patch("app.services.retrieval.QdrantService")
@patch("sentence_transformers.CrossEncoder")
@patch("app.services.llm.AsyncOpenAI")
async def test_ask_endpoint_success(
    mock_openai_class: MagicMock,
    mock_cross_encoder_class: MagicMock,
    mock_qdrant_class: MagicMock,
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    # 1. Mock Qdrant
    mock_qdrant = MagicMock()
    mock_qdrant.health_check.return_value = True
    mock_qdrant.collection_exists.return_value = True
    mock_qdrant.collection_name = "research_documents"
    mock_qdrant_class.return_value = mock_qdrant

    # Mock return context chunk
    mock_hit = MagicMock()
    mock_hit.score = 0.90
    mock_hit.payload = {
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "chunk_index": 2,
        "text": "The model was trained for 50 epochs.",
        "source_filename": "hyperparameters.txt",
        "file_type": ".txt",
    }
    mock_qclient = MagicMock()
    mock_qresponse = MagicMock()
    mock_qresponse.points = [mock_hit]
    mock_qclient.query_points.return_value = mock_qresponse
    mock_qclient.search.return_value = [mock_hit]
    mock_qdrant.connect.return_value = mock_qclient

    # 2. Mock Reranker
    from app.services.reranking import default_reranking_service
    default_reranking_service._model = None
    mock_rerank_instance = MagicMock()
    mock_cross_encoder_class.return_value = mock_rerank_instance
    mock_rerank_instance.predict.return_value = [3.5]

    # 3. Mock OpenAI completions
    mock_openai = MagicMock()
    mock_openai_class.return_value = mock_openai
    
    mock_completion_choice = MagicMock()
    mock_completion_choice.message.content = "According to [S1], the training took 50 epochs."
    mock_completion = MagicMock()
    mock_completion.choices = [mock_completion_choice]
    
    # Mock AsyncOpenAI chat completions create method
    from unittest.mock import AsyncMock
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_completion)

    # Override the fastapi dependencies
    from app.main import app
    from app.services.llm import default_llm_service
    from app.services.qdrant import get_qdrant_service
    
    default_llm_service._client = None
    default_llm_service.api_key = "test-mock-key"
    app.dependency_overrides[get_qdrant_service] = lambda: mock_qdrant

    try:
        # 4. Setup project in DB
        project = Project(id=uuid.uuid4(), name="RAG Ask API Project")
        db_session.add(project)
        await db_session.commit()

        # 5. Call Ask Endpoint
        payload = {
            "query": "How many epochs did training take?",
            "top_k": 3,
        }
        response = await async_client.post(
            f"/api/v1/projects/{project.id}/ask",
            json=payload,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["query"] == payload["query"]
        assert "50 epochs" in data["answer"]
        assert len(data["citations"]) == 1
        assert data["citations"][0]["source_id"] == "S1"
        assert data["citations"][0]["filename"] == "hyperparameters.txt"

    finally:
        app.dependency_overrides.clear()
        default_llm_service.api_key = None


@pytest.mark.asyncio
async def test_ask_endpoint_project_not_found(async_client: httpx.AsyncClient) -> None:
    payload = {"query": "Factual question", "top_k": 5}
    response = await async_client.post(
        f"/api/v1/projects/{uuid.uuid4()}/ask",
        json=payload,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_ask_endpoint_empty_query_fails(async_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    project = Project(id=uuid.uuid4(), name="Ask API Project")
    db_session.add(project)
    await db_session.commit()

    payload = {"query": "  ", "top_k": 5}
    response = await async_client.post(
        f"/api/v1/projects/{project.id}/ask",
        json=payload,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
@patch("app.services.retrieval.QdrantService")
@patch("sentence_transformers.CrossEncoder")
@patch("app.services.llm.AsyncOpenAI")
async def test_ask_endpoint_handles_hallucinated_citation_safely(
    mock_openai_class: MagicMock,
    mock_cross_encoder_class: MagicMock,
    mock_qdrant_class: MagicMock,
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Mock Qdrant
    mock_qdrant = MagicMock()
    mock_qdrant.health_check.return_value = True
    mock_qdrant_class.return_value = mock_qdrant

    mock_hit = MagicMock()
    mock_hit.score = 0.90
    mock_hit.payload = {
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "chunk_index": 0,
        "text": "True evidence block.",
        "source_filename": "true.pdf",
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
    mock_rerank_instance.predict.return_value = [3.0]

    # Mock OpenAI with a response containing a hallucinated S99 citation
    mock_openai = MagicMock()
    mock_openai_class.return_value = mock_openai
    
    mock_completion_choice = MagicMock()
    mock_completion_choice.message.content = "Answer claims something [S1], and invents [S99]."
    mock_completion = MagicMock()
    mock_completion.choices = [mock_completion_choice]
    
    from unittest.mock import AsyncMock
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_completion)

    from app.main import app
    from app.services.llm import default_llm_service
    from app.services.qdrant import get_qdrant_service
    
    default_llm_service._client = None
    default_llm_service.api_key = "test-mock-key"
    app.dependency_overrides[get_qdrant_service] = lambda: mock_qdrant

    try:
        project = Project(id=uuid.uuid4(), name="Ask API Project")
        db_session.add(project)
        await db_session.commit()

        payload = {"query": "Question text", "top_k": 5}
        response = await async_client.post(
            f"/api/v1/projects/{project.id}/ask",
            json=payload,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # S1 should resolve, but the hallucinated S99 must be ignored (not in list)
        assert len(data["citations"]) == 1
        assert data["citations"][0]["source_id"] == "S1"
        assert data["citations"][0]["filename"] == "true.pdf"

    finally:
        app.dependency_overrides.clear()
        default_llm_service.api_key = None

