import asyncio
import logging
import sys
from pathlib import Path

backend_dir = Path(r"C:\Users\Mahesh Karki\Downloads\Mahesh\AI Research Assistant\backend")
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.embedding import ChunkEmbedding
from app.services.embedding import get_embedding_service
from app.services.qdrant import get_qdrant_service
from app.services.indexing import get_indexing_service

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] - %(message)s")

async def force_index():
    async with async_session_factory() as session:
        stmt = select(Document).where(Document.status == "ready")
        res = await session.execute(stmt)
        docs = res.scalars().all()
        
        qdrant_svc = get_qdrant_service()
        emb_svc = get_embedding_service()
        idx_svc = get_indexing_service()

        print(f"Found {len(docs)} ready documents.")
        for doc in docs:
            print(f"Indexing document: {doc.original_filename} (ID: {doc.id}, ProjectID: {doc.project_id})...")
            res_summary = await idx_svc.index_document(
                session=session,
                project_id=doc.project_id,
                document_id=doc.id,
                qdrant_service=qdrant_svc,
                embedding_service=emb_svc,
            )
            print(f"  Summary: {res_summary}")

if __name__ == "__main__":
    asyncio.run(force_index())
