import logging
from typing import List, Dict, Any, Optional
import uuid
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundException
from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.services.document_processing.chunking.recursive import RecursiveChunkingStrategy, count_tokens
from app.services.document_processing.chunking.structural import (
    PDFChunkingStrategy,
    DocxChunkingStrategy,
    CSVChunkingStrategy,
    ExcelChunkingStrategy,
    JSONChunkingStrategy,
)

logger = logging.getLogger("ai_research_assistant.processing.chunking")


class ChunkingService:
    """Orchestrates document chunking strategies, token/character count validation, and DB persistence."""

    def select_strategy(self, file_extension: str) -> Any:
        """Select appropriate chunking strategy based on file format extension."""
        ext = file_extension.lower().strip()
        if ext == ".pdf":
            return PDFChunkingStrategy()
        elif ext in (".docx", ".doc"):
            return DocxChunkingStrategy()
        elif ext == ".csv":
            return CSVChunkingStrategy()
        elif ext in (".xlsx", ".xls"):
            return ExcelChunkingStrategy()
        elif ext == ".json":
            return JSONChunkingStrategy()
        else:
            # Fallback to standard recursive chunking for text/other files
            return RecursiveChunkingStrategy()

    async def chunk_document(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves extracted text, chunks it using the format-specific strategy, and persists results.
        """
        settings = get_settings()
        c_size = chunk_size or settings.CHUNK_SIZE
        c_overlap = chunk_overlap or settings.CHUNK_OVERLAP

        # 1. Fetch document and verify existence
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

        # 2. Verify extracted text exists
        if not document.extracted_text or not document.extracted_text.strip():
            # If document is failed or empty, we return empty chunks without crashing
            # Check if status is failed, maybe keep it failed, or return empty list
            if document.status == "failed":
                return {
                    "document_id": document.id,
                    "chunk_count": 0,
                    "total_characters": 0,
                    "total_tokens": 0,
                }
            # Otherwise we treat it as an empty document
            # Delete old chunks
            await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
            await session.commit()
            return {
                "document_id": document.id,
                "chunk_count": 0,
                "total_characters": 0,
                "total_tokens": 0,
            }

        # 3. Select strategy and chunk text
        strategy = self.select_strategy(document.file_extension)
        raw_chunks = strategy.chunk(document.extracted_text, document, c_size, c_overlap)

        # 4. Filter empty/whitespace-only chunks and build model instances
        chunks_to_save: List[DocumentChunk] = []
        total_chars = 0
        total_tokens = 0

        for idx, rc in enumerate(raw_chunks):
            text = rc["text"].strip()
            if not text:
                continue

            char_count = len(text)
            token_count = count_tokens(text)

            total_chars += char_count
            total_tokens += token_count

            # Build metadata dict with standard required fields + format-specific fields
            chunk_metadata = {
                "document_id": str(document.id),
                "project_id": str(document.project_id),
                "chunk_index": idx,
                "source_filename": document.original_filename,
                "file_type": document.file_extension.lower(),
                **rc.get("metadata", {}),
            }

            db_chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document.id,
                project_id=document.project_id,
                chunk_index=idx,
                text=text,
                character_count=char_count,
                token_count=token_count,
                metadata_=chunk_metadata,
            )
            chunks_to_save.append(db_chunk)

        # 5. Clear old chunks (supports reprocessing/re-chunking idempotency)
        # Using execute delete to be fast and safe
        await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        
        # 6. Bulk persist new chunks
        if chunks_to_save:
            session.add_all(chunks_to_save)

        # Set document status to ready if not already
        document.status = "ready"

        await session.commit()
        await session.refresh(document)

        logger.info(
            f"Chunked document {document.id}: generated {len(chunks_to_save)} chunks "
            f"({total_chars} chars, {total_tokens} tokens)"
        )

        return {
            "document_id": document.id,
            "chunk_count": len(chunks_to_save),
            "total_characters": total_chars,
            "total_tokens": total_tokens,
        }


# Singleton chunking service instance
default_chunking_service = ChunkingService()


def get_chunking_service() -> ChunkingService:
    """FastAPI dependency for ChunkingService."""
    return default_chunking_service
