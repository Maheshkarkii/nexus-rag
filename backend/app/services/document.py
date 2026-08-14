"""Service and repository operations for research document ingestion and metadata lifecycle."""

import logging
import uuid
from collections.abc import Sequence
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.db.models.document import Document
from app.db.models.project import Project
from app.services.storage import StorageService

logger = logging.getLogger("ai_research_assistant.documents")


def validate_uploaded_file(upload_file: UploadFile) -> tuple[str, str]:
    """Validate that the uploaded file has a valid name, allowed extension, and content type."""
    if not upload_file.filename or not upload_file.filename.strip():
        raise BadRequestException(message="File must have a valid non-empty filename.")

    settings = get_settings()
    raw_filename = Path(upload_file.filename).name
    ext = Path(raw_filename).suffix.lower()

    if not ext or ext not in settings.ALLOWED_EXTENSIONS:
        allowed = ", ".join(settings.ALLOWED_EXTENSIONS)
        raise BadRequestException(
            message=f"Unsupported file type '{ext}'. Allowed extensions are: {allowed}"
        )

    mime_type = upload_file.content_type or "application/octet-stream"
    return ext, mime_type


async def create_document(
    session: AsyncSession,
    project_id: uuid.UUID,
    upload_file: UploadFile,
    storage_service: StorageService,
) -> Document:
    """Save an uploaded file to disk and record its metadata in PostgreSQL with compensation cleanup."""
    # 1. Verify project exists
    project_stmt = select(Project).where(Project.id == project_id)
    project_res = await session.execute(project_stmt)
    project = project_res.scalar_one_or_none()
    if not project:
        raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")

    # 2. Validate file extension and MIME type
    ext, mime_type = validate_uploaded_file(upload_file)
    original_filename = Path(upload_file.filename or "unknown").name

    # 3. Generate collision-resistant stored filename
    stored_filename = f"{uuid.uuid4().hex}{ext}"

    # 4. Stream file to project storage directory
    storage_path, file_size = await storage_service.save_file(
        project_id=project_id,
        upload_file=upload_file,
        stored_filename=stored_filename,
    )

    # 5. Persist document metadata in PostgreSQL with transactional compensation
    doc = Document(
        project_id=project_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        storage_path=storage_path,
        mime_type=mime_type,
        file_extension=ext,
        file_size=file_size,
        status="uploaded",
    )
    session.add(doc)

    try:
        await session.commit()
        await session.refresh(doc)
        logger.info(
            f"Successfully ingested document '{original_filename}' (ID: {doc.id}) in project '{project_id}'"
        )
        return doc
    except Exception as exc:
        logger.error(
            f"Database failure storing document metadata for '{original_filename}': {exc}. Rolling back and cleaning file."
        )
        await session.rollback()
        storage_service.delete_file(storage_path)
        raise


async def get_documents_by_project(
    session: AsyncSession, project_id: uuid.UUID
) -> Sequence[Document]:
    """Retrieve all document metadata records for a project ordered by creation date descending."""
    # Verify project exists
    project_stmt = select(Project).where(Project.id == project_id)
    project_res = await session.execute(project_stmt)
    project = project_res.scalar_one_or_none()
    if not project:
        raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")

    stmt = (
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_document_by_id(
    session: AsyncSession, project_id: uuid.UUID, document_id: uuid.UUID
) -> Document | None:
    """Retrieve a single document metadata record verifying that it belongs to the target project."""
    # Verify project exists
    project_stmt = select(Project).where(Project.id == project_id)
    project_res = await session.execute(project_stmt)
    project = project_res.scalar_one_or_none()
    if not project:
        raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")

    stmt = select(Document).where(
        Document.id == document_id,
        Document.project_id == project_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_document(
    session: AsyncSession,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    storage_service: StorageService,
) -> None:
    """Delete a document's physical file from disk and remove its metadata from PostgreSQL."""
    doc = await get_document_by_id(
        session=session, project_id=project_id, document_id=document_id
    )
    if not doc:
        raise NotFoundException(
            message=f"Document with ID '{document_id}' was not found in project '{project_id}'."
        )

    # 1. Delete Qdrant points if Qdrant is running
    try:
        from qdrant_client.http import models as qmodels

        from app.services.qdrant import default_qdrant_service

        if default_qdrant_service.health_check() and default_qdrant_service.collection_exists():
            default_qdrant_service.delete_points(
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="document_id",
                                match=qmodels.MatchValue(value=str(doc.id)),
                            )
                        ]
                    )
                )
            )
            logger.info(f"Successfully deleted Qdrant vector points for document '{document_id}'")
    except Exception as exc:
        logger.error(f"Compensating failure: Qdrant point deletion failed for document '{document_id}': {exc}")
        raise RuntimeError(f"Could not delete vectors from Qdrant: {exc}") from exc

    # 2. Delete physical file
    storage_service.delete_file(doc.storage_path)

    # 3. Delete database record
    await session.delete(doc)
    await session.commit()
    logger.info(f"Successfully deleted document '{document_id}' from project '{project_id}'")
