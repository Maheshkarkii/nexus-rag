
from app.evaluation.evaluator import RAGEvaluator


def test_golden_dataset_loading() -> None:
    evaluator = RAGEvaluator()
    assert len(evaluator.test_cases) >= 4
    categories = {tc["category"] for tc in evaluator.test_cases}
    assert "direct_fact" in categories
    assert "comparison" in categories
    assert "unanswerable" in categories
    assert "structured_data" in categories


def test_rag_evaluator_all_cases() -> None:
    evaluator = RAGEvaluator()
    summary = evaluator.evaluate_all()

    assert summary["total_test_cases"] >= 4
    assert summary["passed_test_cases"] == summary["total_test_cases"]
    assert summary["pass_rate_percent"] == 100.0

    metrics = summary["summary_metrics"]
    assert metrics["avg_recall_at_5"] >= 0.70
    assert metrics["avg_groundedness_score"] >= 0.8


def test_unanswerable_question_evaluation() -> None:
    evaluator = RAGEvaluator()
    unanswerable_case = [tc for tc in evaluator.test_cases if tc["category"] == "unanswerable"][0]

    retrieved = []
    generated_fallback = "I couldn't find enough relevant information in the selected documents."

    res = evaluator.evaluate_test_case(unanswerable_case, retrieved, generated_fallback, latency_ms=12.0)
    assert res["passed"] is True
    assert res["groundedness"]["is_grounded"] is True


def test_structured_data_question_evaluation() -> None:
    evaluator = RAGEvaluator()
    struct_case = [tc for tc in evaluator.test_cases if tc["category"] == "structured_data"][0]

    retrieved = [{"chunk_id": "c1", "text": "employees.csv AI department average salary is 150.", "metadata": {"source_filename": "employees.csv"}}]
    generated_ans = "The average salary in the AI department is 150."

    res = evaluator.evaluate_test_case(struct_case, retrieved, generated_ans, latency_ms=25.0)
    assert res["passed"] is True
    assert res["keyword_coverage"] == 1.0
