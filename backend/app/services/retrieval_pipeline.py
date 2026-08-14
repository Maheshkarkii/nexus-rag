import logging
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.document import Document
from app.services.embedding import EmbeddingService
from app.services.hybrid_retrieval import (
    HybridFusionService,
    LexicalSearchService,
    NearDuplicateDeduplicator,
    default_retrieval_cache,
)
from app.services.qdrant import QdrantService
from app.services.reranking import RerankingService
from app.services.retrieval import RetrievalService

logger = logging.getLogger("ai_research_assistant.services.retrieval_pipeline")


class RetrievalPipeline:
    """Coordinates hybrid (semantic + BM25) retrieval, cross-encoder reranking, near-duplicate removal, and context optimization."""

    def detect_comparison_intent(self, query: str) -> bool:
        """Lightweight regex/keyword classifier to detect comparison intent."""
        query_lc = query.lower()
        patterns = [
            r"\bcompare\b", r"\bcontrast\b", r"\bdifference(s)?\b", r"\bsimilarit(y|ies)\b",
            r"\bvs\b", r"\bversus\b", r"\bdistinguish\b", r"\bdiffer\b",
            r"\bwhich (one|paper|document|dataset|approach|methodology|model)\b",
            r"\bbetween\b", r"\bcomparison\b", r"\bmethodologies\b"
        ]
        return any(re.search(pat, query_lc) for pat in patterns)

    async def retrieve_optimized(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        query: str,
        retrieval_service: RetrievalService,
        reranking_service: RerankingService,
        qdrant_service: QdrantService,
        embedding_service: EmbeddingService,
        top_k: int = 5,
        document_ids: list[uuid.UUID] | None = None,
        file_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch candidates using hybrid semantic + lexical search, rerank using CrossEncoder, prune near-duplicates, and slice to budget."""
        settings = get_settings()

        # Check retrieval cache
        cached = default_retrieval_cache.get(
            str(project_id), query, [str(d) for d in document_ids] if document_ids else None
        )
        if cached is not None:
            return cached[:top_k]

        # If comparison intent is detected, route to comparison pipeline
        if self.detect_comparison_intent(query):
            logger.info("Comparison intent detected. Routing to multi-document comparison pipeline.")
            res = await self.retrieve_comparison(
                session=session,
                project_id=project_id,
                query=query,
                retrieval_service=retrieval_service,
                reranking_service=reranking_service,
                qdrant_service=qdrant_service,
                embedding_service=embedding_service,
                document_ids=document_ids,
                file_types=file_types,
            )
            default_retrieval_cache.put(
                str(project_id), query, res, [str(d) for d in document_ids] if document_ids else None
            )
            return res

        # Stage 23 Hybrid Retrieval Pipeline
        # 1. Broad candidate pool
        candidate_k = max(settings.INITIAL_RETRIEVAL_K, top_k)

        # 2. Semantic vector retrieval
        semantic_candidates = await retrieval_service.retrieve(
            session=session,
            project_id=project_id,
            query=query,
            qdrant_service=qdrant_service,
            embedding_service=embedding_service,
            top_k=candidate_k,
            score_threshold=0.0,
            document_ids=document_ids,
            file_types=file_types,
        )

        if not semantic_candidates:
            return []

        # 3. Lexical BM25 search over candidate pool
        semantic_scores = [float(c.get("score", 0.0)) for c in semantic_candidates]
        lexical_scores = LexicalSearchService.score_chunks(query, semantic_candidates)

        # 4. Fusion and score normalization
        fused_candidates = HybridFusionService.fuse_scores(
            chunks=semantic_candidates,
            semantic_scores=semantic_scores,
            lexical_scores=lexical_scores,
            query=query,
        )

        # 5. Rerank top candidates using CrossEncoder
        rerank_k = min(settings.RERANK_K, len(fused_candidates))
        reranked = reranking_service.rerank(
            query=query,
            candidates=fused_candidates[:rerank_k],
            top_k=rerank_k,
        )

        # 6. Apply relevance thresholding (discard chunks with negligible score)
        threshold = settings.MIN_RELEVANCE_THRESHOLD
        filtered = [c for c in reranked if float(c.get("score", 0.0)) >= threshold]
        if not filtered:
            filtered = reranked[:1] # Keep at least best chunk if any exist

        # 7. Apply near-duplicate reduction
        deduplicated = NearDuplicateDeduplicator.deduplicate(filtered, similarity_threshold=0.75)

        # 8. Apply context optimization (token budget & final_k slicing)
        optimized = self.optimize_context(
            candidates=deduplicated,
            max_tokens=settings.MAX_CONTEXT_TOKENS,
            final_k=top_k,
        )

        # Cache result
        default_retrieval_cache.put(
            str(project_id), query, optimized, [str(d) for d in document_ids] if document_ids else None
        )

        return optimized

    async def retrieve_comparison(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        query: str,
        retrieval_service: RetrievalService,
        reranking_service: RerankingService,
        qdrant_service: QdrantService,
        embedding_service: EmbeddingService,
        document_ids: list[uuid.UUID] | None = None,
        file_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Document-aware retrieval, grouping, reranking, and balancing for comparison queries."""
        settings = get_settings()

        stmt = select(Document).where(Document.project_id == project_id)
        if document_ids:
            stmt = stmt.where(Document.id.in_(document_ids))
        res = await session.execute(stmt)
        docs = res.scalars().all()

        stats_chunks = []
        for doc in docs:
            ext = doc.file_extension.lower()
            meta = doc.extracted_metadata or {}
            stats_text = ""
            if ext == ".csv":
                cols = ", ".join(meta.get("column_names", []))
                stats_text = (
                    f"File Statistics & Structure:\n"
                    f"Filename: {doc.original_filename}\n"
                    f"Row Count: {meta.get('row_count', 'Unknown')} rows\n"
                    f"Column Count: {meta.get('column_count', 'Unknown')} columns\n"
                    f"Columns: {cols}"
                )
            elif ext in (".xlsx", ".xls"):
                sheets_desc = []
                for s in meta.get("sheets", []):
                    sheets_desc.append(f"  - Sheet '{s.get('sheet_name')}' with {s.get('row_count')} rows and {s.get('column_count')} columns")
                sheets_str = "\n".join(sheets_desc)
                stats_text = (
                    f"File Statistics & Structure:\n"
                    f"Filename: {doc.original_filename}\n"
                    f"Sheet Count: {meta.get('sheet_count', 'Unknown')} sheets\n"
                    f"Sheets Info:\n{sheets_str}"
                )
            elif ext == ".json":
                stats_text = (
                    f"File Statistics & Structure:\n"
                    f"Filename: {doc.original_filename}\n"
                    f"Root Type: {meta.get('root_type', 'Unknown')}\n"
                    f"Item/Record Count: {meta.get('item_count', 'Unknown')}"
                )

            if stats_text:
                stats_chunks.append({
                    "chunk_id": uuid.uuid4(),
                    "document_id": doc.id,
                    "project_id": project_id,
                    "text": stats_text,
                    "score": 1.0,
                    "chunk_index": -1,
                    "metadata": {
                        "source_filename": doc.original_filename,
                        "file_type": doc.file_extension,
                    }
                })

        candidate_k = max(settings.INITIAL_RETRIEVAL_K, 50)
        candidates = await retrieval_service.retrieve(
            session=session,
            project_id=project_id,
            query=query,
            qdrant_service=qdrant_service,
            embedding_service=embedding_service,
            top_k=candidate_k,
            score_threshold=0.0,
            document_ids=document_ids,
            file_types=file_types,
        )

        if not candidates and not stats_chunks:
            return []

        # Hybrid fusion on comparison candidates
        semantic_scores = [float(c.get("score", 0.0)) for c in candidates]
        lexical_scores = LexicalSearchService.score_chunks(query, candidates)
        fused_candidates = HybridFusionService.fuse_scores(candidates, semantic_scores, lexical_scores, query)

        grouped: dict[uuid.UUID, list[dict[str, Any]]] = {}
        for doc in docs:
            grouped[doc.id] = []

        for c in fused_candidates:
            doc_id = c["document_id"]
            if doc_id not in grouped:
                grouped[doc_id] = []
            grouped[doc_id].append(c)

        for doc_id, chunks in grouped.items():
            if chunks:
                grouped[doc_id] = reranking_service.rerank(
                    query=query,
                    candidates=chunks,
                    top_k=len(chunks),
                )

        doc_scores = {}
        for doc_id, chunks in grouped.items():
            doc_scores[doc_id] = chunks[0]["score"] if chunks else -1.0

        sorted_doc_ids = sorted(grouped.keys(), key=lambda d: doc_scores[d], reverse=True)
        sorted_doc_ids = sorted_doc_ids[:settings.MAX_DOCUMENTS_FOR_COMPARISON]

        selected_chunks = []
        selected_chunks.extend(stats_chunks)

        current_tokens = 0
        max_tokens = settings.COMPARISON_CONTEXT_BUDGET

        def est_tokens(text: str) -> int:
            return int(len(text.split()) * 1.3)

        for chunk in stats_chunks:
            current_tokens += est_tokens(chunk["text"])

        for step in range(settings.MAX_CHUNKS_PER_DOCUMENT):
            added_any = False
            for doc_id in sorted_doc_ids:
                chunks = grouped[doc_id]
                if step < len(chunks):
                    chunk = chunks[step]
                    tokens = est_tokens(chunk["text"])
                    if current_tokens + tokens <= max_tokens:
                        selected_chunks.append(chunk)
                        current_tokens += tokens
                        added_any = True
            if not added_any:
                break

        return selected_chunks

    def optimize_context(
        self,
        candidates: list[dict[str, Any]],
        max_tokens: int,
        final_k: int,
    ) -> list[dict[str, Any]]:
        """Remove duplicate and near-duplicate chunks, enforcing token and length boundaries."""
        deduped = NearDuplicateDeduplicator.deduplicate(candidates, similarity_threshold=0.75)
        final_list = deduped[:final_k]

        budget_list = []
        current_tokens = 0
        for c in final_list:
            tokens = int(len(c["text"].split()) * 1.3)
            if current_tokens + tokens <= max_tokens:
                budget_list.append(c)
                current_tokens += tokens
            else:
                break

        return budget_list


default_retrieval_pipeline = RetrievalPipeline()


def get_retrieval_pipeline() -> RetrievalPipeline:
    return default_retrieval_pipeline
