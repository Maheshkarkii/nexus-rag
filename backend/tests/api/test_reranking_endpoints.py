import uuid
from unittest.mock import MagicMock, patch
import httpx
import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project


@pytest.mark.asyncio
@patch("app.services.retrieval.QdrantService")
@patch("app.services.reranking.CrossEncoder")
async def test_retrieve_endpoint_with_reranking(
    mock_cross_encoder_class: MagicMock,
    mock_qdrant_class: MagicMock,
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    # 1. Mock Qdrant Service
    mock_qdrant = MagicMock()
    mock_qdrant.health_check.return_value = True
    mock_qdrant.collection_exists.return_value = True
    mock_qdrant.collection_name = "research_documents"
    mock_qdrant_class.return_value = mock_qdrant

    # Mock Qdrant return list (semantic candidates)
    mock_hit = MagicMock()
    mock_hit.score = 0.85
    mock_hit.payload = {
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "chunk_index": 0,
        "text": "The study utilized a convolutional neural network.",
        "source_filename": "cnn_paper.pdf",
        "file_type": ".pdf",
    }
    mock_client = MagicMock()
    mock_client.search.return_value = [mock_hit]
    mock_qdrant.connect.return_value = mock_client

    # 2. Mock Reranker Model
    from app.services.reranking import default_reranking_service
    default_reranking_service._model = None
    mock_rerank_instance = MagicMock()
    mock_cross_encoder_class.return_value = mock_rerank_instance
    mock_rerank_instance.predict.return_value = [4.2]

    # Override the fastapi dependency for QdrantService
    from app.services.qdrant import get_qdrant_service
    from app.main import app
    app.dependency_overrides[get_qdrant_service] = lambda: mock_qdrant

    try:
        # 3. Setup Project in DB
        project = Project(id=uuid.uuid4(), name="Rerank API Project")
        db_session.add(project)
        await db_session.commit()

        # 4. Request retrieval
        payload = {
            "query": "What neural network architecture was used?",
            "top_k": 3,
        }
        response = await async_client.post(
            f"/api/v1/projects/{project.id}/retrieve",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["query"] == payload["query"]
        assert len(data["results"]) == 1
        assert data["results"][0]["score"] == 4.2
        assert data["results"][0]["vector_score"] == 0.85
        assert data["results"][0]["reranker_score"] == 4.2
        assert data["results"][0]["text"] == "The study utilized a convolutional neural network."

    finally:
        app.dependency_overrides.clear()
