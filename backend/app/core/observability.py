import logging
import uuid
import time
import json
import re
from typing import Any, Dict, List, Optional, Set
from contextlib import contextmanager

logger = logging.getLogger("ai_research_assistant.observability")


class TraceSpan:
    """Represents a single timed execution span within a RAG trace."""

    def __init__(self, name: str, trace_id: str) -> None:
        self.name = name
        self.trace_id = trace_id
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.duration_ms: float = 0.0
        self.metadata: Dict[str, Any] = {}
        self.error: Optional[str] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        if exc_val:
            self.error = str(exc_val)
            logger.error(f"[Trace {self.trace_id}] Span '{self.name}' failed after {self.duration_ms}ms: {exc_val}")
        else:
            logger.info(f"[Trace {self.trace_id}] Span '{self.name}' completed in {self.duration_ms}ms")
        return False # Do not suppress exceptions


class RequestCorrelationContext:
    """Manages request and correlation IDs across asynchronous workflow spans."""

    @staticmethod
    def get_correlation_id(request_headers: Optional[Dict[str, str]] = None) -> str:
        """Extract existing correlation ID or generate a new UUID4 string."""
        if request_headers:
            cid = request_headers.get("x-correlation-id") or request_headers.get("X-Correlation-ID")
            if cid:
                return cid
        return f"corr_{uuid.uuid4().hex[:12]}"


class RAGMetricsCollector:
    """In-memory metrics collector for application latency percentiles, tokens, and quality stats."""

    def __init__(self) -> None:
        self.latencies_ms: List[float] = []
        self.token_counts: List[int] = []
        self.errors: Dict[str, int] = {}
        self.request_count: int = 0

    def record_request(self, latency_ms: float, tokens: int = 0, error_type: Optional[str] = None) -> None:
        """Safely record a request event without throwing exceptions."""
        try:
            self.request_count += 1
            if isinstance(latency_ms, (int, float)):
                self.latencies_ms.append(float(latency_ms))
            if isinstance(tokens, int) and tokens > 0:
                self.token_counts.append(tokens)
            if error_type:
                self.errors[str(error_type)] = self.errors.get(str(error_type), 0) + 1
        except Exception as e:
            logger.warning(f"Metrics collection failed: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Compute latency percentiles (P50, P95) and aggregated counts."""
        valid_lat = [float(x) for x in self.latencies_ms if isinstance(x, (int, float))]
        if not valid_lat:
            return {
                "request_count": self.request_count,
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "total_tokens_used": sum(self.token_counts),
                "error_counts": self.errors,
            }

        sorted_lat = sorted(valid_lat)
        n = len(sorted_lat)
        p50_idx = int(0.50 * n)
        p95_idx = min(int(0.95 * n), n - 1)

        return {
            "request_count": self.request_count,
            "p50_latency_ms": round(sorted_lat[p50_idx], 2),
            "p95_latency_ms": round(sorted_lat[p95_idx], 2),
            "avg_latency_ms": round(sum(sorted_lat) / n, 2),
            "total_tokens_used": sum(self.token_counts),
            "error_counts": self.errors,
        }


default_metrics_collector = RAGMetricsCollector()


class GroundednessEvaluator:
    """Evaluates answer groundedness and citation validity against retrieved evidence chunks."""

    @staticmethod
    def evaluate_groundedness(answer: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate if claims in the generated answer are grounded in context chunks."""
        if not answer.strip() or not context_chunks:
            return {"groundedness_score": 0.0, "is_grounded": False, "reason": "Empty answer or context"}

        combined_context = " ".join([c.get("text", "") for c in context_chunks]).lower()
        sentences = [s.strip() for s in re.split(r"[.!?]", answer) if len(s.strip()) > 10]

        if not sentences:
            return {"groundedness_score": 1.0, "is_grounded": True, "reason": "No evaluation sentences"}

        grounded_count = 0
        for sent in sentences:
            # Extract key words (>3 chars) from sentence
            words = [w.lower() for w in re.findall(r"\b\w{4,}\b", sent)]
            if not words:
                grounded_count += 1
                continue
            
            # Sentence is grounded if majority of key terms appear in context
            matched_words = sum(1 for w in words if w in combined_context)
            if matched_words / len(words) >= 0.4:
                grounded_count += 1

        score = round(grounded_count / len(sentences), 2)
        return {
            "groundedness_score": score,
            "is_grounded": score >= 0.7,
            "evaluated_sentences": len(sentences),
            "grounded_sentences": grounded_count,
        }

    @staticmethod
    def evaluate_citations(answer: str, valid_source_ids: Set[str]) -> Dict[str, Any]:
        """Evaluate citation correctness and completeness."""
        cited_tags = re.findall(r"\[S(\d+)\]", answer)
        cited_ids = {f"S{m}" for m in cited_tags}

        invalid_citations = cited_ids - valid_source_ids
        correct_citations = cited_ids.intersection(valid_source_ids)

        correctness_score = round(len(correct_citations) / len(cited_ids), 2) if cited_ids else 1.0

        return {
            "total_citations": len(cited_ids),
            "correct_citations": len(correct_citations),
            "invalid_citations": list(invalid_citations),
            "correctness_score": correctness_score,
            "is_citation_valid": len(invalid_citations) == 0,
        }


class BenchmarkEvaluator:
    """Computes retrieval quality metrics (Recall@K, Precision@K, MRR, Hit Rate) on benchmark test datasets."""

    @staticmethod
    def compute_retrieval_metrics(
        expected_source_filenames: List[str],
        retrieved_chunks: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Compute Recall@K, Precision@K, MRR, and Hit Rate for a retrieval query."""
        if not expected_source_filenames:
            return {"recall_at_k": 0.0, "precision_at_k": 0.0, "mrr": 0.0, "hit_rate": 0.0}

        retrieved_top_k = retrieved_chunks[:top_k]
        retrieved_sources = [
            c.get("metadata", {}).get("source_filename") or c.get("filename", "")
            for c in retrieved_top_k
        ]

        expected_set = set(expected_source_filenames)
        hits = [s for s in retrieved_sources if s in expected_set]
        unique_hits = set(hits)

        # 1. Hit Rate (1 if at least one expected source is in top K, else 0)
        hit_rate = 1.0 if len(hits) > 0 else 0.0

        # 2. Recall@K
        recall_at_k = round(len(unique_hits) / len(expected_set), 2)

        # 3. Precision@K
        precision_at_k = round(len(hits) / len(retrieved_top_k), 2) if retrieved_top_k else 0.0

        # 4. MRR (Mean Reciprocal Rank of first relevant source)
        mrr = 0.0
        for idx, src in enumerate(retrieved_sources, 1):
            if src in expected_set:
                mrr = round(1.0 / idx, 2)
                break

        return {
            "hit_rate": hit_rate,
            "recall_at_k": recall_at_k,
            "precision_at_k": precision_at_k,
            "mrr": mrr,
        }
