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
async def test_retrieve_endpoint_success(
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

    # Mock return list
    mock_hit = MagicMock()
    mock_hit.score = 0.91
    mock_hit.payload = {
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "chunk_index": 1,
        "text": "Extracted evidence text segment",
        "source_filename": "paper.pdf",
        "file_type": ".pdf",
        "page_number": 5,
    }

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.points = [mock_hit]
    mock_client.query_points.return_value = mock_response
    mock_client.search.return_value = [mock_hit]
    mock_qdrant.connect.return_value = mock_client

    # 2. Mock Reranker Model
    from app.services.reranking import default_reranking_service
    default_reranking_service._model = None
    mock_rerank_instance = MagicMock()
    mock_cross_encoder_class.return_value = mock_rerank_instance
    mock_rerank_instance.predict.return_value = [2.5]

    # Override the fastapi dependency for QdrantService
    from app.main import app
    from app.services.qdrant import get_qdrant_service
    app.dependency_overrides[get_qdrant_service] = lambda: mock_qdrant

    try:
        # 3. Setup project in DB
        project = Project(id=uuid.uuid4(), name="Retrieve API Project")
        db_session.add(project)
        await db_session.commit()

        # 4. Call endpoint
        payload = {
            "query": "Evidence findings",
            "top_k": 3,
            "score_threshold": 0.1,
            "document_ids": [],
            "file_types": ["pdf"],
        }
        response = await async_client.post(
            f"/api/v1/projects/{project.id}/retrieve",
            json=payload,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["query"] == "Evidence findings"
        assert len(data["results"]) == 1
        assert data["results"][0]["score"] == 2.5
        assert data["results"][0]["vector_score"] == 0.91
        assert data["results"][0]["reranker_score"] == 2.5
        assert data["results"][0]["text"] == "Extracted evidence text segment"
        assert data["results"][0]["metadata"]["source_filename"] == "paper.pdf"
        assert data["results"][0]["metadata"]["page_number"] == 5

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_retrieve_endpoint_project_not_found(async_client: httpx.AsyncClient) -> None:
    payload = {"query": "Some query"}
    response = await async_client.post(
        f"/api/v1/projects/{uuid.uuid4()}/retrieve",
        json=payload,
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_retrieve_endpoint_invalid_query_validation(
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Setup project in DB
    project = Project(id=uuid.uuid4(), name="Retrieve API Project")
    db_session.add(project)
    await db_session.commit()

    # Empty query string
    payload = {"query": "   "}
    response = await async_client.post(
        f"/api/v1/projects/{project.id}/retrieve",
        json=payload,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
