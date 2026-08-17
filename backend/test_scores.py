import asyncio
import uuid
from app.db.session import async_session_factory
from app.services.retrieval_pipeline import get_retrieval_pipeline
from app.services.retrieval import get_retrieval_service
from app.services.reranking import get_reranking_service
from app.services.qdrant import get_qdrant_service
from app.services.embedding import get_embedding_service

async def test():
    async with async_session_factory() as session:
        pipe = get_retrieval_pipeline()
        res = await pipe.retrieve_optimized(
            session=session,
            project_id=uuid.UUID('d8b7cdd1-ca20-483c-ae65-cb944d77270d'),
            query='What are the two main goals stated at the beginning of Chapter 9?',
            retrieval_service=get_retrieval_service(),
            reranking_service=get_reranking_service(),
            qdrant_service=get_qdrant_service(),
            embedding_service=get_embedding_service(),
            top_k=8,
            document_ids=[uuid.UUID('2125b14b-75ac-40de-9aae-a3b9593b6ac2')]
        )
        print('SCORES:', [(r['score'], r['text'][:100]) for r in res])

if __name__ == '__main__':
    asyncio.run(test())
