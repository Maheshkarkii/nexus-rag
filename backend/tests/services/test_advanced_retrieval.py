import uuid
import pytest

from app.services.hybrid_retrieval import (
    LexicalSearchService,
    MultiQueryExpander,
    SourceDiversifier,
    HybridFusionService,
    NearDuplicateDeduplicator,
    RetrievalCache,
)


def test_multi_query_expander() -> None:
    exp = MultiQueryExpander.expand_query("Transformer efficiency benchmark")
    assert len(exp) >= 2
    assert "Transformer efficiency benchmark" in exp


def test_source_diversifier() -> None:
    # 5 chunks from Doc A, 2 chunks from Doc B
    chunks = [
        {"chunk_id": f"a_{i}", "document_id": "doc_A", "text": f"Doc A content {i}"} for i in range(5)
    ] + [
        {"chunk_id": f"b_{i}", "document_id": "doc_B", "text": f"Doc B content {i}"} for i in range(2)
    ]

    diversified = SourceDiversifier.diversify(chunks, top_k=5)
    doc_a_count = sum(1 for c in diversified if c["document_id"] == "doc_A")
    doc_b_count = sum(1 for c in diversified if c["document_id"] == "doc_B")

    assert doc_a_count <= 3
    assert doc_b_count == 2
    assert len(diversified) == 5


def test_hybrid_fusion_service() -> None:
    chunks = [
        {"text": "ResNet-50 accuracy report"},
        {"text": "Generic image classification background"},
    ]
    sem_scores = [0.90, 0.85]
    lex_scores = [12.5, 0.0]

    fused = HybridFusionService.fuse_scores(chunks, sem_scores, lex_scores, query="ResNet-50")
    assert len(fused) == 2
    assert fused[0]["text"] == "ResNet-50 accuracy report"
    assert fused[0]["score"] > fused[1]["score"]


def test_near_duplicate_deduplication() -> None:
    chunks = [
        {"text": "The ResNet-50 model achieved 93.4% top-5 accuracy on ImageNet dataset."},
        {"text": "The ResNet-50 model achieved 93.4% top-5 accuracy on ImageNet dataset."},  # Identical duplicate
        {"text": "BERT-large transformer model achieved state of the art on SQuAD v1.1."},
    ]

    deduped = NearDuplicateDeduplicator.deduplicate(chunks, similarity_threshold=0.75)
    assert len(deduped) == 2


def test_retrieval_cache_invalidation() -> None:
    cache = RetrievalCache()
    p1 = str(uuid.uuid4())
    chunks = [{"text": "Cached chunk"}]

    cache.put(p1, "sample query", chunks)
    retrieved = cache.get(p1, "sample query")
    assert retrieved is not None
    assert len(retrieved) == 1

    cache.invalidate_project(p1)
    invalidated = cache.get(p1, "sample query")
    assert invalidated is None
