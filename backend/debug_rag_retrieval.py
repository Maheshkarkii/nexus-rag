import asyncio
import logging
import sys
from pathlib import Path

# Force add backend folder to sys.path
backend_dir = Path(r"C:\Users\Mahesh Karki\Downloads\Mahesh\AI Research Assistant\backend")
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select

from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.embedding import ChunkEmbedding
from app.db.session import async_session_factory
from app.services.embedding import EmbeddingService
from app.services.qdrant import get_qdrant_service
from app.services.reranking import get_reranking_service
from app.services.retrieval import RetrievalService
from app.services.retrieval_pipeline import get_retrieval_pipeline

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s")
logger = logging.getLogger("rag_debugger")

queries = [
    "What are the two main goals stated at the beginning of Chapter 9?",
    "Using PyTorch to fight cancer",
    "What is Chapter 9 about?",
    "What does the chapter say about the goals of Part 2?",
    "lung cancer detection",
]

async def debug_retrieval():
    async with async_session_factory() as session:
        # 1. Fetch all existing documents in database
        stmt = select(Document)
        res = await session.execute(stmt)
        docs = res.scalars().all()
        
        print("\n" + "="*80)
        print("1. DOCUMENT INGESTION DIAGNOSTICS")
        print("="*80)
        if not docs:
            print("ERROR: No documents found in database!")
            return

        for doc in docs:
            # Chunks count
            stmt_c = select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            res_c = await session.execute(stmt_c)
            chunks = res_c.scalars().all()
            
            # Embeddings count
            stmt_e = select(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_([c.id for c in chunks])) if chunks else None
            embeddings_count = 0
            if stmt_e is not None:
                res_e = await session.execute(stmt_e)
                embeddings_count = len(res_e.scalars().all())

            print(f"Doc ID: {doc.id}")
            print(f"  Project ID: {doc.project_id}")
            print(f"  Filename: {doc.original_filename}")
            print(f"  Status: {doc.status}")
            print(f"  File Extension: {doc.file_extension}")
            print(f"  Extracted Chars: {doc.extracted_character_count}")
            print(f"  Total Chunks Created: {len(chunks)}")
            print(f"  Total Embeddings Created: {embeddings_count}")
            print(f"  Indexing Status: {doc.indexing_status}")
            print(f"  Indexing Error: {doc.indexing_error}")
            print("-" * 50)

        # 2. Embedding service check
        print("\n" + "="*80)
        print("2. EMBEDDING & VECTOR STORE DIAGNOSTICS")
        print("="*80)
        emb_svc = EmbeddingService()
        emb_svc.load_model()
        print(f"Embedding Model Name: {emb_svc.model_name}")
        print(f"Embedding Dimension: {emb_svc.get_dimension()}")
        
        qdrant_svc = get_qdrant_service()
        qclient = qdrant_svc.connect()
        print(f"Qdrant Client Connected: {qclient}")
        print(f"Qdrant Collection Name: {qdrant_svc.collection_name}")
        
        # 3. Direct Vector Retrieval Tests (Bypassing LLM)
        ret_svc = RetrievalService()
        rerank_svc = get_reranking_service()
        pipeline = get_retrieval_pipeline()
        
        target_project_id = docs[0].project_id
        target_doc_id = docs[0].id

        print("\n" + "="*80)
        print("3. TESTING QUERIES DIRECTLY AGAINST VECTOR STORE & PIPELINE")
        print("="*80)
        
        for q in queries:
            print(f"\n>>> QUERY: '{q}'")
            
            # A. Raw Qdrant Search (No Filter)
            print("  --- A. Raw Vector Search (Scoped only to Project ID) ---")
            raw_res = await ret_svc.retrieve(
                session=session,
                project_id=target_project_id,
                query=q,
                qdrant_service=qdrant_svc,
                embedding_service=emb_svc,
                top_k=5,
                score_threshold=0.0,
                document_ids=None,
            )
            print(f"  Retrieved {len(raw_res)} chunks (raw):")
            for i, chunk in enumerate(raw_res, 1):
                print(f"    [{i}] Score: {chunk.get('score'):.4f} | DocID: {chunk.get('document_id')} | ChunkIndex: {chunk.get('chunk_index')}")
                snippet = chunk.get("text", "").replace("\n", " ")[:200]
                print(f"        Snippet: {snippet}...")

            # B. Raw Qdrant Search (With Document ID Filter)
            print(f"  --- B. Vector Search WITH Document Filter [{target_doc_id}] ---")
            filtered_res = await ret_svc.retrieve(
                session=session,
                project_id=target_project_id,
                query=q,
                qdrant_service=qdrant_svc,
                embedding_service=emb_svc,
                top_k=5,
                score_threshold=0.0,
                document_ids=[target_doc_id],
            )
            print(f"  Retrieved {len(filtered_res)} chunks (with doc_ids filter):")
            for i, chunk in enumerate(filtered_res, 1):
                print(f"    [{i}] Score: {chunk.get('score'):.4f} | ChunkIndex: {chunk.get('chunk_index')}")
                snippet = chunk.get("text", "").replace("\n", " ")[:200]
                print(f"        Snippet: {snippet}...")

            # C. Full Retrieval Pipeline (Hybrid + Reranker + Relevance Threshold)
            print("  --- C. Full Retrieval Pipeline (retrieve_optimized) ---")
            pipeline_res = await pipeline.retrieve_optimized(
                session=session,
                project_id=target_project_id,
                query=q,
                retrieval_service=ret_svc,
                reranking_service=rerank_svc,
                qdrant_service=qdrant_svc,
                embedding_service=emb_svc,
                top_k=5,
                document_ids=[target_doc_id],
            )
            print(f"  Retrieved {len(pipeline_res)} chunks from full pipeline:")
            for i, chunk in enumerate(pipeline_res, 1):
                print(f"    [{i}] Final Score: {chunk.get('score'):.4f} | Reranked Score: {chunk.get('rerank_score')} | ChunkIndex: {chunk.get('chunk_index')}")
                snippet = chunk.get("text", "").replace("\n", " ")[:300]
                print(f"        Snippet: {snippet}...")

if __name__ == "__main__":
    asyncio.run(debug_retrieval())
