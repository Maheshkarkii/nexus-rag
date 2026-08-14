import json
import os
import sys

from app.evaluation.evaluator import RAGEvaluator


def main():
    """Execute RAG Quality & Benchmark Evaluation Suite and print executive summary."""
    print("==========================================================================")
    print("        AI RESEARCH ASSISTANT — STAGE 30 RAG EVALUATION BENCHMARK        ")
    print("==========================================================================")

    evaluator = RAGEvaluator()
    results = evaluator.evaluate_all()

    print(f"Total Test Cases Evaluated : {results['total_test_cases']}")
    print(f"Passed Test Cases         : {results['passed_test_cases']}")
    print(f"Pass Rate Percentage      : {results['pass_rate_percent']}%")
    print(f"Total Execution Duration  : {results['duration_ms']} ms")
    print("--------------------------------------------------------------------------")
    print("SUMMARY METRICS:")
    metrics = results["summary_metrics"]
    print(f"  - Average Recall@5        : {metrics['avg_recall_at_5']}")
    print(f"  - Average Precision@5     : {metrics['avg_precision_at_5']}")
    print(f"  - Average MRR             : {metrics['avg_mrr']}")
    print(f"  - Average Groundedness    : {metrics['avg_groundedness_score']}")
    print("--------------------------------------------------------------------------")

    # Output JSON artifact
    out_dir = os.path.dirname(__file__)
    out_file = os.path.join(out_dir, "evaluation_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"Detailed evaluation report saved to: {out_file}")
    print("==========================================================================")


if __name__ == "__main__":
    main()
