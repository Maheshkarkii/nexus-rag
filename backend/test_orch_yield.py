import asyncio
import uuid
from app.db.session import async_session_factory
from app.services.retrieval_pipeline import get_retrieval_pipeline
from app.services.retrieval import get_retrieval_service
from app.services.reranking import get_reranking_service
from app.services.qdrant import get_qdrant_service
from app.services.embedding import get_embedding_service
from app.services.prompt_builder import get_prompt_builder
from app.services.llm import get_llm_service
from app.services.research import ResearchOrchestrator

async def test():
    async with async_session_factory() as session:
        orch = ResearchOrchestrator(
            llm_service=get_llm_service(),
            retrieval_pipeline=get_retrieval_pipeline(),
            retrieval_service=get_retrieval_service(),
            reranking_service=get_reranking_service(),
            qdrant_service=get_qdrant_service(),
            embedding_service=get_embedding_service(),
            prompt_builder=get_prompt_builder()
        )
        async for chunks in orch.execute_research(
            session=session,
            project_id=uuid.UUID('d8b7cdd1-ca20-483c-ae65-cb944d77270d'),
            query='What are the two main goals stated at the beginning of Chapter 9?',
            document_ids=[uuid.UUID('2125b14b-75ac-40de-9aae-a3b9593b6ac2')]
        ):
            print('CHUNKS YIELDED TYPE:', type(chunks), 'COUNT:', len(chunks) if isinstance(chunks, list) else None)

if __name__ == '__main__':
    asyncio.run(test())
