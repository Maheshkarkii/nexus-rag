import uuid
from unittest.mock import MagicMock, patch

import pytest
from qdrant_client.http import models as qmodels
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.db.models.document import Document
from app.db.models.project import Project
from app.services.embedding import EmbeddingService
from app.services.qdrant import QdrantService
from app.services.retrieval import RetrievalService


@pytest.mark.asyncio
async def test_retrieve_validation_empty_query(db_session: AsyncSession) -> None:
    service = RetrievalService()
    emb_svc = EmbeddingService(device="cpu")
    qdrant_svc = QdrantService()

    with pytest.raises(BadRequestException, match="Query string cannot be empty"):
        await service.retrieve(
            session=db_session,
            project_id=uuid.uuid4(),
            query="   ",
            qdrant_service=qdrant_svc,
            embedding_service=emb_svc,
        )


@pytest.mark.asyncio
async def test_retrieve_validation_invalid_document_ids(db_session: AsyncSession) -> None:
    service = RetrievalService()
    emb_svc = EmbeddingService(device="cpu")
    qdrant_svc = QdrantService()

    project = Project(id=uuid.uuid4(), name="P1")
    db_session.add(project)
    await db_session.commit()

    # D1 belongs to project, but D2 is non-existent
    doc1 = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="d1.txt",
        stored_filename="d1_stored.txt",
        storage_path="projects/d1.txt",
        mime_type="text/plain",
        file_extension=".txt",
        file_size=100,
        status="ready",
    )
    db_session.add(doc1)
    await db_session.commit()

    with pytest.raises(BadRequestException, match="Validation failed: The following document IDs do not exist"):
        await service.retrieve(
            session=db_session,
            project_id=project.id,
            query="methodology",
            qdrant_service=qdrant_svc,
            embedding_service=emb_svc,
            document_ids=[doc1.id, uuid.uuid4()], # invalid doc ID present
        )


@pytest.mark.asyncio
@patch("app.services.retrieval.QdrantService")
async def test_retrieve_constructs_correct_qdrant_filters(
    mock_qdrant_class: MagicMock,
    db_session: AsyncSession,
) -> None:
    # 1. Setup DB
    project = Project(id=uuid.uuid4(), name="Ret Workspace")
    db_session.add(project)
    await db_session.commit()

    doc = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="d1.txt",
        stored_filename="d1_stored.txt",
        storage_path="projects/d1.txt",
        mime_type="text/plain",
        file_extension=".txt",
        file_size=100,
        status="ready",
    )
    db_session.add(doc)
    await db_session.commit()

    # 2. Mock Qdrant
    mock_qdrant = MagicMock()
    mock_qdrant.health_check.return_value = True
    mock_qdrant.collection_exists.return_value = True
    mock_qdrant.collection_name = "research_documents"
    mock_qdrant_class.return_value = mock_qdrant

    # Mock search response
    mock_hit = MagicMock()
    mock_hit.score = 0.85
    mock_hit.payload = {
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(doc.id),
        "project_id": str(project.id),
        "chunk_index": 0,
        "text": "The study used a convolutional neural network...",
        "source_filename": "d1.txt",
        "file_type": ".txt",
        "custom_tag": "tag1",
    }
    
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.points = [mock_hit]
    mock_client.query_points.return_value = mock_response
    mock_client.search.return_value = [mock_hit]
    mock_qdrant.connect.return_value = mock_client

    # 3. Call retrieve
    service = RetrievalService()
    emb_svc = EmbeddingService(device="cpu")
    
    results = await service.retrieve(
        session=db_session,
        project_id=project.id,
        query="convolutional neural network",
        qdrant_service=mock_qdrant,
        embedding_service=emb_svc,
        top_k=3,
        score_threshold=0.5,
        document_ids=[doc.id],
        file_types=["txt"],
    )

    assert len(results) == 1
    assert results[0]["score"] == 0.85
    assert results[0]["text"] == "The study used a convolutional neural network..."
    assert results[0]["metadata"]["custom_tag"] == "tag1"
    assert results[0]["metadata"]["source_filename"] == "d1.txt"

    # Verify qmodels filter calls
    if mock_client.query_points.called:
        kwargs = mock_client.query_points.call_args[1]
    else:
        kwargs = mock_client.search.call_args[1]
    assert kwargs["limit"] == 3
    assert kwargs["score_threshold"] == 0.5
    
    # Inspect qmodels filter parameter structure
    qfilter = kwargs["query_filter"]
    assert isinstance(qfilter, qmodels.Filter)
    
    # Must have 3 conditions: project_id, document_id, and file_type
    assert len(qfilter.must) == 3
    assert qfilter.must[0].key == "project_id"
    assert qfilter.must[0].match.value == str(project.id)
    assert qfilter.must[1].key == "document_id"
    assert qfilter.must[1].match.any == [str(doc.id)]
    assert qfilter.must[2].key == "file_type"
    assert qfilter.must[2].match.any == [".txt"]
