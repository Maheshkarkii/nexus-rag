import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.db.models.document import Document
from app.services.hybrid_retrieval import (
    LexicalSearchService,
    HybridFusionService,
    NearDuplicateDeduplicator,
    RetrievalCache,
)
from app.services.retrieval_pipeline import RetrievalPipeline
from app.services.embedding import EmbeddingService
from app.services.prompt_builder import PromptBuilder


def test_lexical_bm25_search() -> None:
    chunks = [
        {"id": "c1", "text": "The model utilizes a ResNet-50 convolutional architecture for image classification."},
        {"id": "c2", "text": "BERT-large achieves state-of-the-art results on NLP benchmark datasets."},
        {"id": "c3", "text": "Random background text about climate change."}
    ]

    scores = LexicalSearchService.score_chunks("BERT-large NLP benchmark", chunks)
    assert len(scores) == 3
    # BERT-large chunk should have highest BM25 score
    assert scores[1] > scores[0]
    assert scores[1] > scores[2]


def test_score_normalization_and_fusion() -> None:
    chunks = [
        {"id": "c1", "text": "BERT-large evaluation", "score": 0.8},
        {"id": "c2", "text": "General deep learning", "score": 0.9}
    ]

    semantic_scores = [0.8, 0.9]
    lexical_scores = [10.5, 0.0]

    fused = HybridFusionService.fuse_scores(
        chunks=chunks,
        semantic_scores=semantic_scores,
        lexical_scores=lexical_scores,
        query="BERT-large"
    )

    assert len(fused) == 2
    # BERT-large candidate should receive exact keyword boost
    assert fused[0]["id"] == "c1"
    assert "retrieval_metadata" in fused[0]


def test_near_duplicate_deduplication() -> None:
    chunks = [
        {"id": "c1", "text": "The ResNet-50 architecture was evaluated on ImageNet dataset achieving 93.4 percent accuracy."},
        {"id": "c2", "text": "The ResNet-50 architecture was evaluated on ImageNet dataset achieving 93.4 percent accuracy."}, # Exact duplicate
        {"id": "c3", "text": "BERT-large model was evaluated on SQuAD dataset."}
    ]

    unique = NearDuplicateDeduplicator.deduplicate(chunks, similarity_threshold=0.75)
    assert len(unique) == 2
    assert unique[0]["id"] == "c1"
    assert unique[1]["id"] == "c3"


def test_retrieval_cache() -> None:
    cache = RetrievalCache(ttl_seconds=60)
    p_id = str(uuid.uuid4())
    query = "What is BERT-large?"
    data = [{"id": "c1", "text": "BERT-large chunk"}]

    cache.put(p_id, query, data)
    hit = cache.get(p_id, query)
    assert hit is not None
    assert hit[0]["id"] == "c1"

    # Invalidate project
    cache.invalidate_project(p_id)
    miss = cache.get(p_id, query)
    assert miss is None


@pytest.mark.asyncio
@patch("app.services.retrieval.QdrantService")
async def test_end_to_end_hybrid_pipeline(
    mock_qdrant_class: MagicMock,
    db_session: AsyncSession
) -> None:
    project = Project(id=uuid.uuid4(), name="Hybrid Workspace")
    db_session.add(project)
    await db_session.commit()

    doc = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="bert.pdf",
        stored_filename="bert_stored.pdf",
        storage_path="projects/bert.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size=100,
        status="ready",
    )
    db_session.add(doc)
    await db_session.commit()

    mock_qdrant = MagicMock()
    mock_qdrant_class.return_value = mock_qdrant

    mock_retrieval_svc = AsyncMock()
    mock_retrieval_svc.retrieve.return_value = [
        {"chunk_id": uuid.uuid4(), "document_id": doc.id, "project_id": project.id, "text": "BERT-large achieves 94% accuracy on SQuAD.", "score": 0.85},
        {"chunk_id": uuid.uuid4(), "document_id": doc.id, "project_id": project.id, "text": "Irrelevant background text about oceanography.", "score": 0.1}
    ]

    mock_rerank_svc = MagicMock()
    mock_rerank_svc.rerank.side_effect = lambda query=None, candidates=None, top_k=None, **kwargs: candidates

    pipeline = RetrievalPipeline()
    emb_svc = EmbeddingService(device="cpu")

    results = await pipeline.retrieve_optimized(
        session=db_session,
        project_id=project.id,
        query="BERT-large SQuAD accuracy",
        retrieval_service=mock_retrieval_svc,
        reranking_service=mock_rerank_svc,
        qdrant_service=mock_qdrant,
        embedding_service=emb_svc,
        top_k=5,
    )

    assert len(results) >= 1
    assert "BERT-large" in results[0]["text"]
    assert "retrieval_metadata" in results[0]
