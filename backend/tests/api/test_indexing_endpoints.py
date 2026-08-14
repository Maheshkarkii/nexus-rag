import uuid
from unittest.mock import MagicMock, patch
import httpx
import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.embedding import ChunkEmbedding
from app.db.models.project import Project


@pytest.mark.asyncio
@patch("app.services.indexing.QdrantService")
async def test_index_document_endpoint_success(
    mock_qdrant_class: MagicMock,
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Mock Qdrant client methods
    mock_qdrant = MagicMock()
    mock_qdrant.collection_exists.return_value = True
    mock_qdrant.health_check.return_value = True
    mock_qdrant.collection_name = "research_documents"
    mock_qdrant_class.return_value = mock_qdrant

    # Override the fastapi dependency for QdrantService
    from app.services.qdrant import get_qdrant_service
    from app.main import app
    app.dependency_overrides[get_qdrant_service] = lambda: mock_qdrant

    try:
        # 1. Setup project, document, chunk, and embedding in DB
        project = Project(id=uuid.uuid4(), name="Indexing API Workspace", description="Desc")
        db_session.add(project)
        await db_session.commit()

        document = Document(
            id=uuid.uuid4(),
            project_id=project.id,
            original_filename="sample_index.txt",
            stored_filename="sample_index_stored.txt",
            storage_path="projects/test/sample_index.txt",
            mime_type="text/plain",
            file_extension=".txt",
            file_size=100,
            status="ready",
            extracted_text="Some text",
            extracted_character_count=9,
            indexing_status="pending",
        )
        db_session.add(document)
        await db_session.commit()

        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=document.id,
            project_id=project.id,
            chunk_index=0,
            text="Some text",
            character_count=9,
            token_count=2,
            metadata_={},
        )
        db_session.add(chunk)
        await db_session.commit()

        embedding = ChunkEmbedding(
            id=uuid.uuid4(),
            chunk_id=chunk.id,
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            dimension=384,
            vector=[0.1] * 384,
            normalized=True,
            status="completed",
        )
        db_session.add(embedding)
        await db_session.commit()

        # 2. Call POST /index
        response = await async_client.post(
            f"/api/v1/projects/{project.id}/documents/{document.id}/index"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["document_id"] == str(document.id)
        assert data["chunk_count"] == 1
        assert data["indexed_count"] == 1
        assert data["failed_count"] == 0
        assert data["collection_name"] == "research_documents"

        # Verify DB status updated
        doc_stmt = select(Document).where(Document.id == document.id)
        doc_res = await db_session.execute(doc_stmt)
        updated_doc = doc_res.scalar_one()
        assert updated_doc.indexing_status == "indexed"
        assert updated_doc.indexed_at is not None

    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_index_document_missing_embeddings(
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    project = Project(id=uuid.uuid4(), name="Indexing API Workspace", description="Desc")
    db_session.add(project)
    await db_session.commit()

    # Document has chunk but no embedding
    document = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="sample_index.txt",
        stored_filename="sample_index_stored.txt",
        storage_path="projects/test/sample_index.txt",
        mime_type="text/plain",
        file_extension=".txt",
        file_size=100,
        status="ready",
        extracted_text="Some text",
        extracted_character_count=9,
    )
    db_session.add(document)
    await db_session.commit()

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=document.id,
        project_id=project.id,
        chunk_index=0,
        text="Some text",
        character_count=9,
        token_count=2,
    )
    db_session.add(chunk)
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/projects/{project.id}/documents/{document.id}/index"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["error"]["code"] == "BAD_REQUEST"


@pytest.mark.asyncio
@patch("app.services.qdrant.default_qdrant_service")
async def test_delete_document_deletes_qdrant_points(
    mock_qdrant: MagicMock,
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    mock_qdrant.health_check.return_value = True
    mock_qdrant.collection_exists.return_value = True

    project = Project(id=uuid.uuid4(), name="Delete Workspace", description="Desc")
    db_session.add(project)
    await db_session.commit()

    document = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="sample_del.txt",
        stored_filename="sample_del_stored.txt",
        storage_path="projects/test/sample_del.txt",
        mime_type="text/plain",
        file_extension=".txt",
        file_size=100,
        status="ready",
    )
    db_session.add(document)
    await db_session.commit()

    # Call DELETE /documents/{id}
    response = await async_client.delete(
        f"/api/v1/projects/{project.id}/documents/{document.id}"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Qdrant delete_points should be called
    mock_qdrant.delete_points.assert_called_once()
