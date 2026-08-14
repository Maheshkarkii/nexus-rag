import json
import logging
import os
import time
from typing import Any

from app.core.observability import BenchmarkEvaluator, GroundednessEvaluator

logger = logging.getLogger("ai_research_assistant.evaluation")


class RAGEvaluator:
    """Evaluates RAG pipeline quality across golden benchmark datasets, drift detection, and experiment tracking."""

    @staticmethod
    def detect_quality_drift(baseline_results: dict[str, Any], current_results: dict[str, Any], threshold_percent: float = 5.0) -> dict[str, Any]:
        """Compare current benchmark results against baseline metrics to detect quality drift."""
        base_pass = baseline_results.get("pass_rate_percent", 100.0)
        curr_pass = current_results.get("pass_rate_percent", 100.0)
        drift_delta = round(base_pass - curr_pass, 2)
        has_drift = drift_delta > threshold_percent

        base_ground = baseline_results.get("summary_metrics", {}).get("avg_groundedness_score", 1.0)
        curr_ground = current_results.get("summary_metrics", {}).get("avg_groundedness_score", 1.0)
        ground_delta = round(base_ground - curr_ground, 2)

        return {
            "has_quality_drift": has_drift,
            "pass_rate_baseline": base_pass,
            "pass_rate_current": curr_pass,
            "pass_rate_degradation": drift_delta,
            "groundedness_degradation": ground_delta,
            "status": "DRIFT_DETECTED" if has_drift else "STABLE",
            "recommendation": "Review recent retrieval or prompt configuration changes." if has_drift else "Baseline stability maintained.",
        }

    def __init__(self, dataset_path: str | None = None) -> None:
        if not dataset_path:
            base_dir = os.path.dirname(__file__)
            dataset_path = os.path.join(base_dir, "golden_dataset.json")
        
        self.dataset_path = dataset_path
        self.test_cases: list[dict[str, Any]] = []
        self._load_dataset()

    def _load_dataset(self) -> None:
        if os.path.exists(self.dataset_path):
            with open(self.dataset_path, encoding="utf-8") as f:
                self.test_cases = json.load(f)
        else:
            logger.warning(f"Golden dataset not found at '{self.dataset_path}'.")

    def evaluate_test_case(
        self,
        test_case: dict[str, Any],
        retrieved_chunks: list[dict[str, Any]],
        generated_answer: str,
        latency_ms: float = 0.0,
    ) -> dict[str, Any]:
        """Evaluate a single test case against retrieval, generation, and citation quality standards."""
        expected_sources = test_case.get("expected_sources", [])
        is_answerable = test_case.get("is_answerable", True)

        # 1. Retrieval Metrics
        retrieval_metrics = BenchmarkEvaluator.compute_retrieval_metrics(
            expected_source_filenames=expected_sources,
            retrieved_chunks=retrieved_chunks,
            top_k=5,
        )

        # 2. Generation & Groundedness Metrics
        if not is_answerable:
            # For unanswerable questions, answer should indicate insufficient evidence
            has_fallback = "insufficient" in generated_answer.lower() or "couldn't find" in generated_answer.lower()
            groundedness = {
                "groundedness_score": 1.0 if has_fallback else 0.0,
                "is_grounded": has_fallback,
                "reason": "Unanswerable hallucination check",
            }
        else:
            groundedness = GroundednessEvaluator.evaluate_groundedness(
                answer=generated_answer,
                context_chunks=retrieved_chunks,
            )

        # 3. Citation Validation
        valid_source_ids = {f"S{i+1}" for i in range(len(retrieved_chunks))}
        citation_metrics = GroundednessEvaluator.evaluate_citations(
            answer=generated_answer,
            valid_source_ids=valid_source_ids,
        )

        # 4. Keyword Coverage Check
        expected_keywords = test_case.get("expected_keywords", [])
        matched_kw = [kw for kw in expected_keywords if kw.lower() in generated_answer.lower()]
        keyword_coverage = len(matched_kw) / len(expected_keywords) if expected_keywords else 1.0

        return {
            "test_case_id": test_case.get("id"),
            "category": test_case.get("category"),
            "question": test_case.get("question"),
            "is_answerable": is_answerable,
            "latency_ms": round(latency_ms, 2),
            "retrieval_metrics": retrieval_metrics,
            "groundedness": groundedness,
            "citation_metrics": citation_metrics,
            "keyword_coverage": round(keyword_coverage, 2),
            "passed": (
                (retrieval_metrics["hit_rate"] == 1.0 or not is_answerable)
                and groundedness["is_grounded"]
                and citation_metrics["is_citation_valid"]
            ),
        }

    def evaluate_all(self, mock_runner: Any | None = None) -> dict[str, Any]:
        """Run full evaluation suite across all golden dataset cases."""
        results = []
        start_time = time.time()

        for case in self.test_cases:
            case_start = time.time()
            if mock_runner:
                retrieved, answer = mock_runner(case)
            else:
                # Default synthetic mock for baseline evaluation
                kw_text = " ".join(case.get("expected_keywords", []))
                if case["is_answerable"]:
                    retrieved = [
                        {"chunk_id": f"c_{i}", "text": f"Research document {src} details {kw_text}.", "metadata": {"source_filename": src}}
                        for i, src in enumerate(case["expected_sources"])
                    ]
                    answer = f"Based on research [S1], {kw_text}."
                else:
                    retrieved = []
                    answer = "I couldn't find enough relevant information in the selected documents."

            lat_ms = (time.time() - case_start) * 1000
            res = self.evaluate_test_case(case, retrieved, answer, lat_ms)
            results.append(res)

        total_duration = round((time.time() - start_time) * 1000, 2)
        total_cases = len(results)
        passed_cases = sum(1 for r in results if r["passed"])
        pass_rate = round((passed_cases / total_cases) * 100, 2) if total_cases > 0 else 0.0

        avg_recall = round(sum(r["retrieval_metrics"]["recall_at_k"] for r in results) / total_cases, 2) if total_cases > 0 else 0.0
        avg_precision = round(sum(r["retrieval_metrics"]["precision_at_k"] for r in results) / total_cases, 2) if total_cases > 0 else 0.0
        avg_mrr = round(sum(r["retrieval_metrics"]["mrr"] for r in results) / total_cases, 2) if total_cases > 0 else 0.0
        avg_groundedness = round(sum(r["groundedness"]["groundedness_score"] for r in results) / total_cases, 2) if total_cases > 0 else 0.0

        return {
            "evaluation_timestamp": time.time(),
            "total_test_cases": total_cases,
            "passed_test_cases": passed_cases,
            "pass_rate_percent": pass_rate,
            "duration_ms": total_duration,
            "summary_metrics": {
                "avg_recall_at_5": avg_recall,
                "avg_precision_at_5": avg_precision,
                "avg_mrr": avg_mrr,
                "avg_groundedness_score": avg_groundedness,
            },
            "detailed_results": results,
        }
