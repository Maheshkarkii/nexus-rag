import uuid

import httpx
import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.project import Project


@pytest.mark.asyncio
async def test_chunk_document_success(async_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    # 1. Setup project and document with extracted text in DB
    project = Project(id=uuid.uuid4(), name="Endpoint Workspace", description="Desc")
    db_session.add(project)
    await db_session.commit()

    document = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="sample.txt",
        stored_filename="sample_stored.txt",
        storage_path="projects/test/sample.txt",
        mime_type="text/plain",
        file_extension=".txt",
        file_size=100,
        status="ready",
        extracted_text="Sentence one. Sentence two. Sentence three. Sentence four.",
        extracted_character_count=58,
    )
    db_session.add(document)
    await db_session.commit()

    # 2. Call POST chunk endpoint
    response = await async_client.post(
        f"/api/v1/projects/{project.id}/documents/{document.id}/chunk"
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["document_id"] == str(document.id)
    assert data["chunk_count"] > 0
    assert data["total_characters"] > 0
    assert data["total_tokens"] > 0

    # 3. Call GET chunks endpoint to inspect results
    get_res = await async_client.get(
        f"/api/v1/projects/{project.id}/documents/{document.id}/chunks?limit=2&offset=0"
    )
    assert get_res.status_code == status.HTTP_200_OK
    chunks_list = get_res.json()
    assert len(chunks_list) <= 2
    assert chunks_list[0]["document_id"] == str(document.id)
    assert "text" in chunks_list[0]
    assert "token_count" in chunks_list[0]
    assert "character_count" in chunks_list[0]
    assert chunks_list[0]["metadata"]["source_filename"] == "sample.txt"


@pytest.mark.asyncio
async def test_chunk_document_missing_content(async_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    # Setup project and document WITHOUT extracted text
    project = Project(id=uuid.uuid4(), name="Endpoint Workspace", description="Desc")
    db_session.add(project)
    await db_session.commit()

    document = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="sample.txt",
        stored_filename="sample_stored.txt",
        storage_path="projects/test/sample.txt",
        mime_type="text/plain",
        file_extension=".txt",
        file_size=100,
        status="uploaded",  # Not processed yet
        extracted_text=None,
    )
    db_session.add(document)
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/projects/{project.id}/documents/{document.id}/chunk"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "BAD_REQUEST"


@pytest.mark.asyncio
async def test_chunk_document_not_found(async_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    # Call with random IDs
    response = await async_client.post(
        f"/api/v1/projects/{uuid.uuid4()}/documents/{uuid.uuid4()}/chunk"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_chunks_not_found(async_client: httpx.AsyncClient) -> None:
    response = await async_client.get(
        f"/api/v1/projects/{uuid.uuid4()}/documents/{uuid.uuid4()}/chunks"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
