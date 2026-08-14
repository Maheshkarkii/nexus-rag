"""Document processing service orchestrating parsing, normalization, and metadata persistence."""

import logging
from pathlib import Path
import time
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import NotFoundException
from app.db.base import utc_now
from app.db.models.document import Document
from app.db.models.project import Project
from app.services.document_processing.normalizer import normalize_extracted_text
from app.services.document_processing.registry import get_processor_for_document
from app.services.storage import StorageService, get_storage_service

logger = logging.getLogger("ai_research_assistant.processing")


class DocumentProcessingService:
    """Orchestrates file format detection, text extraction, normalization, and state persistence."""

    async def process_document(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        storage_service: StorageService,
    ) -> Document:
        """Execute text extraction pipeline on target document with atomic state transitions."""
        # 1. Verify project exists
        p_res = await session.execute(select(Project).where(Project.id == project_id))
        if not p_res.scalar_one_or_none():
            raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")

        # 2. Verify document exists for this project
        doc_res = await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.project_id == project_id,
            )
        )
        document = doc_res.scalar_one_or_none()
        if not document:
            raise NotFoundException(
                message=f"Document with ID '{document_id}' was not found in project '{project_id}'."
            )

        # 3. Transition status to 'processing' and commit
        document.status = "processing"
        document.processing_error = None
        await session.commit()
        await session.refresh(document)

        start_time = time.perf_counter()
        logger.info(
            f"Started processing document '{document.original_filename}' (ID: {document_id}) for project '{project_id}'"
        )

        try:
            # 4. Locate physical file
            abs_file_path = storage_service.resolve_safe_path(document.storage_path)
            if not abs_file_path.exists() or not abs_file_path.is_file():
                raise FileNotFoundError(
                    f"Physical storage file is missing for document '{document.original_filename}'."
                )

            # 5. Determine processor
            processor = get_processor_for_document(document)
            logger.info(f"Selected processor {processor.__class__.__name__} for doc {document_id}")

            # 6. Extract content
            extraction = await processor.extract(abs_file_path, document)

            # 7. Normalize text
            normalized_text = normalize_extracted_text(extraction.text)
            if not normalized_text:
                raise ValueError("Document yielded 0 characters of readable extracted text.")

            # 8. Update document to 'ready'
            document.status = "ready"
            document.extracted_text = normalized_text
            document.extracted_character_count = len(normalized_text)
            document.extracted_word_count = len(normalized_text.split())
            document.extracted_metadata = extraction.metadata
            document.processing_error = None
            document.processed_at = utc_now()

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                f"Successfully processed doc {document_id} in {duration_ms}ms "
                f"({document.extracted_character_count} chars, {document.extracted_word_count} words)"
            )

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            clean_error = str(exc)
            # Remove any local filesystem paths from the user-facing error message
            if "Physical storage file is missing" in clean_error:
                clean_error = "Physical file is missing from server storage."

            logger.error(
                f"Processing failed for document {document_id} after {duration_ms}ms: {exc}"
            )
            document.status = "failed"
            document.extracted_text = None
            document.extracted_character_count = None
            document.extracted_word_count = None
            document.processing_error = clean_error
            document.processed_at = utc_now()

        # 9. Save final status in PostgreSQL
        await session.commit()
        await session.refresh(document)
        return document


# Singleton processing service
default_processing_service = DocumentProcessingService()


def get_processing_service() -> DocumentProcessingService:
    """FastAPI dependency for DocumentProcessingService."""
    return default_processing_service
