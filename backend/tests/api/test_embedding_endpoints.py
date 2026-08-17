import uuid

import httpx
import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.project import Project


@pytest.mark.asyncio
async def test_embed_document_endpoint_success(async_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    # 1. Setup project, document and chunks in DB
    project = Project(id=uuid.uuid4(), name="Embed API Workspace", description="Desc")
    db_session.add(project)
    await db_session.commit()

    document = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="sample_embed.txt",
        stored_filename="sample_embed_stored.txt",
        storage_path="projects/test/sample_embed.txt",
        mime_type="text/plain",
        file_extension=".txt",
        file_size=100,
        status="ready",
        extracted_text="Sentence one. Sentence two. Sentence three.",
        extracted_character_count=43,
    )
    db_session.add(document)
    await db_session.commit()

    # Create manual chunk
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=document.id,
        project_id=project.id,
        chunk_index=0,
        text="Sentence one. Sentence two. Sentence three.",
        character_count=43,
        token_count=10,
        metadata_={},
    )
    db_session.add(chunk)
    await db_session.commit()

    # 2. POST /embed
    response = await async_client.post(
        f"/api/v1/projects/{project.id}/documents/{document.id}/embed"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["document_id"] == str(document.id)
    assert data["chunk_count"] == 1
    assert data["embedded_count"] == 1
    assert data["failed_count"] == 0
    assert data["dimension"] == 384

    # 3. GET /embeddings (Inspection)
    get_res = await async_client.get(
        f"/api/v1/projects/{project.id}/documents/{document.id}/embeddings?limit=5"
    )
    assert get_res.status_code == status.HTTP_200_OK
    emb_list = get_res.json()
    assert len(emb_list) == 1
    assert emb_list[0]["chunk_id"] == str(chunk.id)
    assert emb_list[0]["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert emb_list[0]["dimension"] == 384
    assert emb_list[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_embed_document_no_chunks(async_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    project = Project(id=uuid.uuid4(), name="Embed API Workspace", description="Desc")
    db_session.add(project)
    await db_session.commit()

    # Document has no chunks
    document = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="sample_embed.txt",
        stored_filename="sample_embed_stored.txt",
        storage_path="projects/test/sample_embed.txt",
        mime_type="text/plain",
        file_extension=".txt",
        file_size=100,
        status="ready",
        extracted_text="Sentence one.",
        extracted_character_count=13,
    )
    db_session.add(document)
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/projects/{project.id}/documents/{document.id}/embed"
    )
    # Should throw BadRequest because chunking wasn't run
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["error"]["code"] == "BAD_REQUEST"


@pytest.mark.asyncio
async def test_embed_document_not_found(async_client: httpx.AsyncClient) -> None:
    # Random IDs
    response = await async_client.post(
        f"/api/v1/projects/{uuid.uuid4()}/documents/{uuid.uuid4()}/embed"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_embeddings_not_found(async_client: httpx.AsyncClient) -> None:
    response = await async_client.get(
        f"/api/v1/projects/{uuid.uuid4()}/documents/{uuid.uuid4()}/embeddings"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
