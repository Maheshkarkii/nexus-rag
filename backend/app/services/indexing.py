import logging
import uuid
from typing import Any

from qdrant_client.http import models as qmodels
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.db.base import utc_now
from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.embedding import ChunkEmbedding
from app.services.embedding import EmbeddingService
from app.services.qdrant import QdrantService

logger = logging.getLogger("ai_research_assistant.services.indexing")


class VectorIndexingService:
    """Orchestrates loading embeddings/payloads and batch upserting them into Qdrant."""

    async def index_document(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        qdrant_service: QdrantService,
        embedding_service: EmbeddingService,
    ) -> dict[str, Any]:
        """Verify embeddings exist, match vector dimensions, build payloads, and batch index to Qdrant."""
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

        # 2. Update status to 'indexing'
        document.indexing_status = "indexing"
        document.indexing_error = None
        await session.commit()
        await session.refresh(document)

        # 3. Check if chunks and embeddings exist using a join (after commit to avoid expired attributes)
        stmt = (
            select(DocumentChunk, ChunkEmbedding)
            .outerjoin(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        result = await session.execute(stmt)
        rows = result.all()  # List of (DocumentChunk, ChunkEmbedding) tuples
        
        if not rows:
            raise BadRequestException(
                message="No chunks found for this document. Run chunking and embedding first."
            )

        # Verify all chunks have completed embeddings
        missing_embeddings = []
        for chunk, emb in rows:
            if emb is None or emb.status != "completed":
                missing_embeddings.append(chunk.chunk_index)

        if missing_embeddings:
            missing_str = ", ".join(str(idx) for idx in missing_embeddings[:5])
            if len(missing_embeddings) > 5:
                missing_str += "..."
            raise BadRequestException(
                message=f"Missing embeddings for chunks: [{missing_str}]. Please run embedding generation first."
            )

        start_time = utc_now()
        logger.info(f"Started indexing document '{document.original_filename}' (ID: {document_id}) into Qdrant...")

        try:
            # 4. Ensure collection exists and is compatible
            dimension = embedding_service.get_dimension()
            distance_metric = "Cosine" if embedding_service.normalize else "Dot"
            qdrant_service.ensure_collection(dimension=dimension, distance_metric=distance_metric)

            # 5. Build Qdrant PointStruct list
            points = []
            for chunk, emb in rows:
                point_id = str(chunk.id)  # Stable UUID point ID mapping directly to DocumentChunk
                
                # Payload mapping
                payload = {
                    "chunk_id": str(chunk.id),
                    "document_id": str(document.id),
                    "project_id": str(document.project_id),
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "source_filename": document.original_filename,
                    "file_type": document.file_extension.lower(),
                }
                
                # Merge format-specific metadata
                if chunk.metadata_:
                    for key, val in chunk.metadata_.items():
                        # Protect core payload fields
                        if key not in payload and val is not None:
                            # Handle serialization safety
                            if isinstance(val, uuid.UUID):
                                payload[key] = str(val)
                            else:
                                payload[key] = val

                points.append(
                    qmodels.PointStruct(
                        id=point_id,
                        vector=emb.vector,
                        payload=payload,
                    )
                )

            # Dimension check validation
            for pt in points:
                if len(pt.vector) != dimension:
                    raise ValueError(
                        f"Vector size mismatch for chunk ID {pt.id}. Expected {dimension}, found {len(pt.vector)}."
                    )

            # 6. Batch upsert to Qdrant
            settings = get_settings()
            batch_size = settings.QDRANT_UPSERT_BATCH_SIZE
            logger.info(f"Upserting {len(points)} vector points in batches of {batch_size}...")

            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                qdrant_service.upsert_points(batch)

            # 7. Update status to 'indexed'
            document.indexing_status = "indexed"
            document.indexed_at = utc_now()
            document.indexing_error = None
            await session.commit()
            
            duration = (utc_now() - start_time).total_seconds()
            logger.info(f"Successfully indexed document {document_id} in {duration:.2f}s.")

            return {
                "document_id": document.id,
                "chunk_count": len(rows),
                "indexed_count": len(points),
                "failed_count": 0,
                "collection_name": qdrant_service.collection_name,
            }

        except Exception as exc:
            # 8. Compensate database status to 'failed'
            logger.error(f"Vector indexing failed for document {document_id}: {exc}")
            document.indexing_status = "failed"
            document.indexing_error = str(exc)
            await session.commit()
            raise RuntimeError(f"Qdrant indexing failed: {exc}") from exc


# Singleton indexing service instance
default_indexing_service = VectorIndexingService()


def get_indexing_service() -> VectorIndexingService:
    """FastAPI dependency for VectorIndexingService."""
    return default_indexing_service
