import asyncio
import logging
import sys
import uuid
from pathlib import Path

backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import UploadFile
from sqlalchemy import select

from app.db.models.project import Project
from app.db.session import async_session_factory
from app.services.document import create_document
from app.services.document_processing.chunking.service import get_chunking_service
from app.services.document_processing.service import get_processing_service
from app.services.embedding import get_embedding_service
from app.services.indexing import get_indexing_service
from app.services.llm import get_llm_service
from app.services.prompt_builder import get_prompt_builder
from app.services.qdrant import get_qdrant_service
from app.services.rag import get_rag_service
from app.services.reranking import get_reranking_service
from app.services.retrieval import RetrievalService
from app.services.retrieval_pipeline import get_retrieval_pipeline

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] - %(message)s")

REQUIRED_QUESTIONS = [
    "What is this document about?",
    "What problem does the paper address?",
    "What is the Transformer architecture?",
    "Why does the paper argue that attention is sufficient?",
    "What are the main components of the Transformer?",
    "How does self-attention work?",
    "What datasets were used?",
    "What were the main experimental results?",
    "How does the Transformer compare with recurrent models?",
]

async def test_attention_pdf_rag():
    print("\n========================================================")
    print("STARTING ATTENTION.PDF END-TO-END RAG INTEGRATION TEST")
    print("========================================================\n")

    # Locate Attention.pdf
    possible_paths = [
        Path(r"C:\Users\Mahesh Karki\Downloads\Attention.pdf"),
        Path(r"C:\Users\Mahesh Karki\Downloads\Mahesh\Attention.pdf"),
        Path(r"C:\Users\Mahesh Karki\Downloads\Mahesh\AI Research Assistant\Attention.pdf"),
        Path(r"C:\Users\Mahesh Karki\Downloads\Mahesh\AI Research Assistant\data\Attention.pdf"),
        Path(r"C:\Users\Mahesh Karki\Downloads\Mahesh\AI Research Assistant\storage\Attention.pdf"),
    ]
    pdf_path = None
    for p in possible_paths:
        if p.exists():
            pdf_path = p
            break

    if not pdf_path:
        # Search in workspace
        found = list(Path(r"C:\Users\Mahesh Karki\Downloads").rglob("Attention.pdf"))
        if found:
            pdf_path = found[0]

    assert pdf_path and pdf_path.exists(), "Attention.pdf file not found for RAG test!"
    print(f"Using test PDF file: {pdf_path}")

    async with async_session_factory() as session:
        # 1. Create or get test project
        stmt = select(Project).where(Project.name == "Attention PDF Test Project")
        res = await session.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            project = Project(
                id=uuid.uuid4(),
                name="Attention PDF Test Project",
                description="Test project for RAG validation on Attention.pdf",
            )
            session.add(project)
            await session.commit()
            await session.refresh(project)
        print(f"Test Project ID: {project.id}")

        # 2. Upload Document
        from app.services.storage import get_storage_service
        storage_svc = get_storage_service()
        
        with open(pdf_path, "rb") as f:
            upload_file = UploadFile(filename="Attention.pdf", file=f)
            doc = await create_document(
                session=session,
                project_id=project.id,
                upload_file=upload_file,
                storage_service=storage_svc,
            )
        print(f"1. UPLOAD: PASS (Doc ID: {doc.id})")

        # 3. Extraction
        proc_svc = get_processing_service()
        doc = await proc_svc.process_document(
            session=session,
            project_id=project.id,
            document_id=doc.id,
            storage_service=storage_svc,
        )
        assert len(doc.extracted_text) > 0, "Extracted text length must be > 0"
        print(f"2. EXTRACTION: PASS (Extracted {len(doc.extracted_text)} chars)")

        # 4. Chunking
        chunk_svc = get_chunking_service()
        chunk_res = await chunk_svc.chunk_document(
            session=session,
            project_id=project.id,
            document_id=doc.id,
        )
        assert chunk_res["chunk_count"] > 0, "Chunk count must be > 0"
        print(f"3. CHUNKING: PASS (Generated {chunk_res['chunk_count']} chunks)")

        # 5. Embedding
        emb_svc = get_embedding_service()
        emb_res = await emb_svc.embed_document(
            session=session,
            project_id=project.id,
            document_id=doc.id,
        )
        assert emb_res["embedded_count"] > 0, "Embedded count must be > 0"
        print(f"4. EMBEDDING: PASS (Generated {emb_res['embedded_count']} embeddings)")

        # 6. Vector Store Indexing
        qdrant_svc = get_qdrant_service()
        idx_svc = get_indexing_service()
        idx_res = await idx_svc.index_document(
            session=session,
            project_id=project.id,
            document_id=doc.id,
            qdrant_service=qdrant_svc,
            embedding_service=emb_svc,
        )
        assert idx_res["indexed_count"] > 0, "Indexed count must be > 0"
        await session.refresh(doc)
        assert doc.status == "ready", "Document status must be ready after indexing"
        print(f"5. VECTOR STORE & READY STATUS: PASS (Indexed {idx_res['indexed_count']} points)")

        # 7. Retrieval & LLM Question Answering
        retrieval_svc = RetrievalService()
        retrieval_pipe = get_retrieval_pipeline()
        rerank_svc = get_reranking_service()
        llm_svc = get_llm_service()
        prompt_bld = get_prompt_builder()
        rag_svc = get_rag_service()

        print("\n========================================================")
        print("RUNNING REQUIRED RAG QUESTIONS")
        print("========================================================\n")

        for q in REQUIRED_QUESTIONS:
            print(f"Question: '{q}'")
            ans_res = await rag_svc.ask_question(
                session=session,
                project_id=project.id,
                query=q,
                retrieval_pipeline=retrieval_pipe,
                retrieval_service=retrieval_svc,
                reranking_service=rerank_svc,
                qdrant_service=qdrant_svc,
                embedding_service=emb_svc,
                prompt_builder=prompt_bld,
                llm_service=llm_svc,
                top_k=5,
                document_ids=[doc.id],
            )
            print(f"Answer snippet: {ans_res['answer'][:200]}...")
            print(f"Citations returned: {len(ans_res.get('citations', []))}")
            assert ans_res['answer'] and "couldn't find enough relevant information" not in ans_res['answer'].lower(), f"RAG failed for query: {q}"
            print("Status: PASS\n------------------------------------------------")

        print("ALL ATTENTION.PDF RAG TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_attention_pdf_rag())
