import uuid
from unittest.mock import MagicMock, patch
import pytest
from app.services.reranking import RerankingService
from app.services.retrieval_pipeline import RetrievalPipeline


@patch("app.services.reranking.CrossEncoder")
def test_reranker_model_loading_and_prediction(mock_cross_encoder_class: MagicMock) -> None:
    mock_instance = MagicMock()
    mock_cross_encoder_class.return_value = mock_instance
    mock_instance.predict.return_value = [1.2, -0.5, 3.4]

    service = RerankingService(model_name="mock-reranker", device="cpu")
    candidates = [
        {"text": "Chunk 1", "score": 0.8},
        {"text": "Chunk 2", "score": 0.7},
        {"text": "Chunk 3", "score": 0.6},
    ]

    reranked = service.rerank("Query", candidates, top_k=2)
    
    # Assert model loaded and predict called
    mock_cross_encoder_class.assert_called_once()
    mock_instance.predict.assert_called_once()

    # Verify scores and sorting
    assert len(reranked) == 2
    assert reranked[0]["text"] == "Chunk 3"  # Score 3.4
    assert reranked[0]["reranker_score"] == 3.4
    assert reranked[0]["vector_score"] == 0.6
    assert reranked[1]["text"] == "Chunk 1"  # Score 1.2
    assert reranked[1]["reranker_score"] == 1.2
    assert reranked[1]["vector_score"] == 0.8


def test_context_optimizer_deduplication_and_overlap() -> None:
    pipeline = RetrievalPipeline()
    candidates = [
        {"text": "Deduplicated identical text block.", "score": 1.0},
        {"text": "Deduplicated identical text block.", "score": 0.9},  # exact duplicate
        {"text": "Deduplicated identical text block slightly diff.", "score": 0.8},  # high Jaccard overlap (> 0.85)
        {"text": "A completely unique independent text chunk.", "score": 0.7},
    ]

    optimized = pipeline.optimize_context(
        candidates=candidates,
        max_tokens=1000,
        final_k=5,
    )

    # Expected: Chunks 2 (exact duplicate) and 3 (near-duplicate) are pruned
    assert len(optimized) == 2
    assert optimized[0]["text"] == "Deduplicated identical text block."
    assert optimized[1]["text"] == "A completely unique independent text chunk."


def test_context_optimizer_token_budget_limiting() -> None:
    pipeline = RetrievalPipeline()
    candidates = [
        {"text": "Word " * 100, "score": 1.0},  # ~130 tokens
        {"text": "Word " * 100, "score": 0.9},  # ~130 tokens
        {"text": "Word " * 100, "score": 0.8},  # ~130 tokens
    ]

    # Set tiny max budget of 200 tokens
    optimized = pipeline.optimize_context(
        candidates=candidates,
        max_tokens=200,
        final_k=5,
    )

    # Should only return 1 chunk since adding the second would exceed 200 tokens (130 * 2 = 260)
    assert len(optimized) == 1
