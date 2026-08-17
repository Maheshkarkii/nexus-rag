
from app.core.observability import (
    BenchmarkEvaluator,
    GroundednessEvaluator,
    RAGMetricsCollector,
)


def test_evaluation_benchmark_metrics() -> None:
    expected_sources = ["paper_a.pdf", "paper_b.pdf"]
    retrieved_chunks = [
        {"chunk_id": "c1", "metadata": {"source_filename": "paper_a.pdf"}},
        {"chunk_id": "c2", "metadata": {"source_filename": "paper_c.pdf"}},
        {"chunk_id": "c3", "metadata": {"source_filename": "paper_b.pdf"}},
    ]

    metrics = BenchmarkEvaluator.compute_retrieval_metrics(
        expected_source_filenames=expected_sources,
        retrieved_chunks=retrieved_chunks,
        top_k=3,
    )

    assert metrics["hit_rate"] == 1.0
    assert metrics["recall_at_k"] == 1.0  # Both paper_a and paper_b are in top 3
    assert metrics["mrr"] == 1.0  # paper_a is at rank 1


def test_groundedness_evaluator_valid() -> None:
    context_chunks = [
        {"text": "ResNet-50 achieves 93.4 percent accuracy on ImageNet classification dataset."}
    ]

    grounded_answer = "ResNet-50 achieves 93.4 percent accuracy on ImageNet dataset."
    hallucinated_answer = "Quantum computing uses supercomputers to solve dark energy physics equations."

    res_grounded = GroundednessEvaluator.evaluate_groundedness(grounded_answer, context_chunks)
    res_hallucinated = GroundednessEvaluator.evaluate_groundedness(hallucinated_answer, context_chunks)

    assert res_grounded["is_grounded"] is True
    assert res_grounded["groundedness_score"] >= 0.7

    assert res_hallucinated["is_grounded"] is False
    assert res_hallucinated["groundedness_score"] < 0.5


def test_citation_evaluator_correctness() -> None:
    valid_source_ids = {"S1", "S2"}
    answer_with_valid = "According to recent studies [S1], deep learning works well [S2]."
    answer_with_invalid = "According to invalid sources [S99], physics is solved."

    val_result = GroundednessEvaluator.evaluate_citations(answer_with_valid, valid_source_ids)
    inval_result = GroundednessEvaluator.evaluate_citations(answer_with_invalid, valid_source_ids)

    assert val_result["is_citation_valid"] is True
    assert val_result["correctness_score"] == 1.0

    assert inval_result["is_citation_valid"] is False
    assert "S99" in inval_result["invalid_citations"]


def test_observability_metrics_collector() -> None:
    collector = RAGMetricsCollector()

    # Record 5 request events
    collector.record_request(latency_ms=100.0, tokens=50)
    collector.record_request(latency_ms=200.0, tokens=60)
    collector.record_request(latency_ms=300.0, tokens=70)
    collector.record_request(latency_ms=400.0, tokens=80)
    collector.record_request(latency_ms=500.0, tokens=90, error_type="llm_error")

    summary = collector.get_summary()

    assert summary["request_count"] == 5
    assert summary["p50_latency_ms"] == 300.0
    assert summary["p95_latency_ms"] == 500.0
    assert summary["total_tokens_used"] == 350
    assert summary["error_counts"].get("llm_error") == 1


def test_observability_failure_isolation() -> None:
    collector = RAGMetricsCollector()
    # Passing invalid inputs should not crash or throw exceptions
    collector.record_request(latency_ms=None)  # type: ignore
    summary = collector.get_summary()
    assert isinstance(summary, dict)
