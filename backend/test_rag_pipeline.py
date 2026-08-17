import asyncio
import logging
import sys
from pathlib import Path

backend_dir = Path(r"C:\Users\Mahesh Karki\Downloads\Mahesh\AI Research Assistant\backend")
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select

from app.db.models.document import Document
from app.db.session import async_session_factory
from app.services.embedding import get_embedding_service
from app.services.indexing import get_indexing_service
from app.services.qdrant import get_qdrant_service
from app.services.retrieval import RetrievalService
from app.services.retrieval_pipeline import get_retrieval_pipeline

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] - %(message)s")

async def test_in_memory_rag():
    async with async_session_factory() as session:
        # Get target document
        stmt = select(Document)
        res = await session.execute(stmt)
        docs = res.scalars().all()
        target_doc = docs[0]
        
        # Shared Qdrant instance for both indexing and retrieval!
        qdrant_svc = get_qdrant_service()
        emb_svc = get_embedding_service()
        idx_svc = get_indexing_service()

        print("=== Step 1: Indexing document into in-memory Qdrant ===")
        res_summary = await idx_svc.index_document(
            session=session,
            project_id=target_doc.project_id,
            document_id=target_doc.id,
            qdrant_service=qdrant_svc,
            embedding_service=emb_svc,
        )
        print(f"Index Summary: {res_summary}\n")

        print("=== Step 2: Testing Queries against same Qdrant instance ===")
        retrieval_svc = RetrievalService()
        pipeline = get_retrieval_pipeline()

        queries = [
            "What are the two main goals stated at the beginning of Chapter 9?",
            "Using PyTorch to fight cancer",
            "What is Chapter 9 about?",
            "What does the chapter say about the goals of Part 2?",
            "lung cancer detection"
        ]

        for q in queries:
            print("\n==================================================")
            print(f"QUERY: '{q}'")
            print("==================================================")
            
            # Raw search
            raw_results = await retrieval_svc.retrieve(
                session=session,
                project_id=target_doc.project_id,
                query=q,
                qdrant_service=qdrant_svc,
                embedding_service=emb_svc,
                top_k=5,
                score_threshold=0.0
            )
            print(f"A. Raw Vector Search (Scoped to Project): {len(raw_results)} chunks returned")
            for i, r in enumerate(raw_results[:3], 1):
                print(f"   [{i}] Score: {r['score']:.4f} | Chunk ID: {r['chunk_id']}")
                snippet = r['text'][:150].encode('ascii', 'ignore').decode('ascii')
                print(f"       Text snippet: {snippet}...")

            # Filtered search
            filtered_results = await retrieval_svc.retrieve(
                session=session,
                project_id=target_doc.project_id,
                query=q,
                qdrant_service=qdrant_svc,
                embedding_service=emb_svc,
                top_k=5,
                document_ids=[target_doc.id],
                score_threshold=0.0
            )
            print(f"B. Vector Search WITH Document Filter: {len(filtered_results)} chunks returned")

            # Full pipeline
            from app.services.reranking import get_reranking_service
            rerank_svc = get_reranking_service()
            opt_results = await pipeline.retrieve_optimized(
                session=session,
                project_id=target_doc.project_id,
                query=q,
                retrieval_service=retrieval_svc,
                reranking_service=rerank_svc,
                qdrant_service=qdrant_svc,
                embedding_service=emb_svc,
                document_ids=[target_doc.id]
            )
            print(f"C. Full Hybrid Pipeline: {len(opt_results)} chunks returned")
            for i, r in enumerate(opt_results[:5], 1):
                chunk_idx = r.get("chunk_index")
                score = r.get("score", 0.0)
                v_score = r.get("vector_score", 0.0)
                b_score = r.get("bm25_score", 0.0)
                rr_score = r.get("rerank_score", 0.0)
                meta = r.get("metadata", {})
                snippet = r.get("text", "")[:300].encode('ascii', 'ignore').decode('ascii')
                print(f"   [{i}] Score: {score:.4f} (vector: {v_score:.4f}, bm25: {b_score:.4f}, rerank: {rr_score:.4f})")
                print(f"       Chunk Index: {chunk_idx} | Page/Metadata: {meta}")
                print(f"       Content Snippet: {snippet}\n")

if __name__ == "__main__":
    asyncio.run(test_in_memory_rag())
