import logging
import uuid
from typing import Any

from qdrant_client.http import models as qmodels
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.db.models.document import Document
from app.services.embedding import EmbeddingService
from app.services.qdrant import QdrantService

logger = logging.getLogger("ai_research_assistant.services.retrieval")


class RetrievalService:
    """Handles semantic querying by embedding query text and executing Qdrant similarity searches with filters."""

    async def retrieve(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        query: str,
        qdrant_service: QdrantService,
        embedding_service: EmbeddingService,
        top_k: int = 5,
        score_threshold: float | None = 0.0,
        document_ids: list[uuid.UUID] | None = None,
        file_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Run similarity queries against Qdrant, scoped strictly to project_id and document/file-type parameters."""
        # 1. Input query string verification
        if not query or not query.strip():
            raise BadRequestException("Query string cannot be empty or whitespace only.")

        # 2. Document ID project validation
        if document_ids:
            # Query documents belonging to the project
            stmt = select(Document.id).where(
                Document.id.in_(document_ids),
                Document.project_id == project_id,
            )
            res = await session.execute(stmt)
            valid_doc_ids = set(res.scalars().all())

            invalid_ids = [d_id for d_id in document_ids if d_id not in valid_doc_ids]
            if invalid_ids:
                invalid_str = ", ".join(str(i_id) for i_id in invalid_ids[:5])
                if len(invalid_ids) > 5:
                    invalid_str += "..."
                raise BadRequestException(
                    message=f"Validation failed: The following document IDs do not exist or belong to another project: [{invalid_str}]."
                )

        # 3. Generate query vector embedding using the configured model
        query_vector = embedding_service.embed_text(query)
        if not query_vector:
            raise BadRequestException("Failed to generate embedding for the search query.")

        dimension = embedding_service.get_dimension()
        if len(query_vector) != dimension:
            raise ValueError(
                f"Dimension mismatch: Query embedding size is {len(query_vector)}, expected {dimension}."
            )

        # 4. Construct Qdrant filters
        must_filters = [
            qmodels.FieldCondition(
                key="project_id",
                match=qmodels.MatchValue(value=str(project_id)),
            )
        ]

        if document_ids:
            must_filters.append(
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchAny(any=[str(d_id) for d_id in document_ids]),
                )
            )

        if file_types:
            cleaned_types = []
            for ft in file_types:
                ft_clean = ft.lower().strip()
                if not ft_clean.startswith("."):
                    ft_clean = f".{ft_clean}"
                cleaned_types.append(ft_clean)

            must_filters.append(
                qmodels.FieldCondition(
                    key="file_type",
                    match=qmodels.MatchAny(any=cleaned_types),
                )
            )

        qfilter = qmodels.Filter(must=must_filters)

        # 5. Connect and execute vector search
        logger.info(
            f"Retrieving top_{top_k} chunks for project {project_id} (threshold={score_threshold}, doc_count={len(document_ids) if document_ids else 'all'})"
        )
        
        try:
            if not qdrant_service.health_check() or not qdrant_service.collection_exists():
                logger.warning("Qdrant collection or connection unavailable for search.")
                return []
            client = qdrant_service.connect()
            if hasattr(client, "query_points"):
                response = client.query_points(
                    collection_name=qdrant_service.collection_name,
                    query=query_vector,
                    query_filter=qfilter,
                    limit=top_k,
                    score_threshold=score_threshold if score_threshold and score_threshold > 0.0 else None,
                )
                search_results = response.points
            else:
                search_results = client.search(
                    collection_name=qdrant_service.collection_name,
                    query_vector=query_vector,
                    query_filter=qfilter,
                    limit=top_k,
                    score_threshold=score_threshold if score_threshold and score_threshold > 0.0 else None,
                )

            # 6. Map results
            mapped_results = []
            for hit in search_results:
                payload = hit.payload or {}
                
                # Exclude primary payload properties from metadata dict
                primary_keys = {"chunk_id", "document_id", "project_id", "chunk_index", "text"}
                meta = {k: v for k, v in payload.items() if k not in primary_keys}

                mapped_results.append(
                    {
                        "chunk_id": uuid.UUID(payload.get("chunk_id")),
                        "document_id": uuid.UUID(payload.get("document_id")),
                        "project_id": uuid.UUID(payload.get("project_id")),
                        "text": payload.get("text", ""),
                        "score": hit.score,
                        "vector_score": hit.score,
                        "chunk_index": payload.get("chunk_index", 0),
                        "metadata": meta,
                    }
                )

            return mapped_results

        except Exception as exc:
            logger.error(f"Semantic search query execution failed in Qdrant: {exc}")
            raise RuntimeError(f"Semantic retrieval failed: {exc}") from exc


# Singleton retrieval service instance
default_retrieval_service = RetrievalService()


def get_retrieval_service() -> RetrievalService:
    """FastAPI dependency for RetrievalService."""
    return default_retrieval_service
