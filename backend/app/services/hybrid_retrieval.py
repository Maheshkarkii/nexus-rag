import logging
import re
import hashlib
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from rank_bm25 import BM25Okapi

from app.core.config import get_settings

logger = logging.getLogger("ai_research_assistant.services.hybrid_retrieval")


def tokenize_text(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric terms for BM25 lexical matching."""
    if not text:
        return []
    return [t.lower() for t in re.findall(r"\b\w+(?:-\w+)*\b", text)]


class LexicalSearchService:
    """BM25 lexical keyword search matcher for exact technical terms and abbreviations."""

    @staticmethod
    def score_chunks(query: str, chunks: List[Dict[str, Any]]) -> List[float]:
        """Compute BM25 scores for a query across candidate chunks."""
        if not chunks or not query.strip():
            return [0.0] * len(chunks)

        tokenized_corpus = [tokenize_text(c.get("text", "")) for c in chunks]
        tokenized_query = tokenize_text(query)

        if not tokenized_query or not any(tokenized_corpus):
            return [0.0] * len(chunks)

        try:
            bm25 = BM25Okapi(tokenized_corpus)
            scores = bm25.get_scores(tokenized_query)
            return [float(s) for s in scores]
        except Exception as e:
            logger.warning(f"BM25 scoring failed: {e}. Returning zeros.")
            return [0.0] * len(chunks)


class MultiQueryExpander:
    """Expands queries into bounded search variations without hallucinating facts."""

    @staticmethod
    def expand_query(query: str) -> List[str]:
        """Generate safe, bounded query variations."""
        queries = [query]
        q_lower = query.lower()

        if "efficiency" in q_lower:
            queries.append(query.replace("efficiency", "computational complexity and throughput"))
        elif "accuracy" in q_lower:
            queries.append(query.replace("accuracy", "evaluation metrics and performance"))
        elif "compare" in q_lower:
            queries.append(f"{query} benchmark differences and key specifications")

        return list(dict.fromkeys(queries))[:3]

    @staticmethod
    def fuse_rrf(rankings: List[List[Dict[str, Any]]], k: int = 60) -> List[Dict[str, Any]]:
        """Reciprocal Rank Fusion (RRF) across candidate lists."""
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Dict[str, Any]] = {}

        for rank_list in rankings:
            for rank, chunk in enumerate(rank_list):
                cid = str(chunk.get("chunk_id") or chunk.get("id") or hash(chunk.get("text", "")))
                chunk_map[cid] = chunk
                score = 1.0 / (k + rank + 1)
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score

        fused = []
        for cid, score in rrf_scores.items():
            c = dict(chunk_map[cid])
            c["rrf_score"] = round(score, 4)
            fused.append(c)

        fused.sort(key=lambda x: x.get("rrf_score", 0.0), reverse=True)
        return fused


class SourceDiversifier:
    """Caps maximum chunks per document to ensure source diversity in context window."""

    MAX_CHUNKS_PER_DOC = 3

    @classmethod
    def diversify(cls, chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """Slice chunks enforcing per-document max limits."""
        doc_counts: Dict[str, int] = {}
        diversified = []

        for chunk in chunks:
            doc_id = str(chunk.get("document_id") or chunk.get("metadata", {}).get("source_filename", "default"))
            count = doc_counts.get(doc_id, 0)

            if count < cls.MAX_CHUNKS_PER_DOC:
                diversified.append(chunk)
                doc_counts[doc_id] = count + 1

            if len(diversified) >= top_k:
                break

        return diversified


class HybridFusionService:
    """Fuses semantic vector scores and lexical BM25 scores using score normalization and weighted linear combination."""

    @staticmethod
    def normalize_bm25(scores: List[float]) -> List[float]:
        """Normalize BM25 scores relative to max score."""
        if not scores:
            return []
        max_val = max(scores)
        if max_val <= 0:
            return [0.0] * len(scores)
        return [s / max_val for s in scores]

    @classmethod
    def fuse_scores(
        cls,
        chunks: List[Dict[str, Any]],
        semantic_scores: List[float],
        lexical_scores: List[float],
        query: str,
    ) -> List[Dict[str, Any]]:
        """Fuse normalized semantic and lexical scores, applying exact-keyword boosts."""
        settings = get_settings()
        norm_lexical = cls.normalize_bm25(lexical_scores)

        query_lc = query.lower()
        exact_terms = [t for t in tokenize_text(query) if len(t) > 3]

        fused_chunks = []
        for idx, chunk in enumerate(chunks):
            sem_s = max(0.0, min(1.0, float(semantic_scores[idx]))) if idx < len(semantic_scores) else 0.0
            lex_s = norm_lexical[idx] if idx < len(norm_lexical) else 0.0

            hybrid_score = (settings.SEMANTIC_WEIGHT * sem_s) + (settings.LEXICAL_WEIGHT * lex_s)

            chunk_text = chunk.get("text", "").lower()
            boost = 0.0
            for term in exact_terms:
                if term in chunk_text:
                    boost += 0.1

            final_score = round(min(1.0, hybrid_score + boost), 4)

            c_copy = dict(chunk)
            c_copy["score"] = final_score
            c_copy["vector_score"] = float(semantic_scores[idx]) if idx < len(semantic_scores) else float(c_copy.get("vector_score", 0.0))
            c_copy["retrieval_metadata"] = {
                "semantic_score": round(semantic_scores[idx], 4) if idx < len(semantic_scores) else 0.0,
                "lexical_score": round(lexical_scores[idx], 4) if idx < len(lexical_scores) else 0.0,
                "norm_semantic": round(sem_s, 4),
                "norm_lexical": round(lex_s, 4),
                "keyword_boost": round(boost, 4),
                "hybrid_score": final_score,
            }
            fused_chunks.append(c_copy)

        fused_chunks.sort(key=lambda c: c["score"], reverse=True)
        return fused_chunks


class NearDuplicateDeduplicator:
    """Detects and removes near-duplicate text fragments using Jaccard token n-gram overlap."""

    @staticmethod
    def get_ngrams(text: str, n: int = 3) -> Set[str]:
        tokens = tokenize_text(text)
        if len(tokens) < n:
            return {" ".join(tokens)}
        return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}

    @classmethod
    def jaccard_similarity(cls, text1: str, text2: str, n: int = 3) -> float:
        w1 = set(tokenize_text(text1))
        w2 = set(tokenize_text(text2))
        word_sim = len(w1.intersection(w2)) / len(w1.union(w2)) if (w1 and w2) else 0.0

        set1 = cls.get_ngrams(text1, n)
        set2 = cls.get_ngrams(text2, n)
        ngram_sim = len(set1.intersection(set2)) / len(set1.union(set2)) if (set1 and set2) else 0.0

        # Substring / token containment check
        if w1 and w2:
            containment = len(w1.intersection(w2)) / min(len(w1), len(w2))
        else:
            containment = 0.0

        return max(word_sim, ngram_sim, containment)

    @classmethod
    def deduplicate(cls, chunks: List[Dict[str, Any]], similarity_threshold: float = 0.75) -> List[Dict[str, Any]]:
        """Remove near-duplicate chunks that exceed similarity threshold."""
        unique_chunks = []
        for chunk in chunks:
            text = chunk.get("text", "")
            is_dup = False
            for existing in unique_chunks:
                sim = cls.jaccard_similarity(text, existing.get("text", ""))
                if sim >= similarity_threshold:
                    is_dup = True
                    break
            if not is_dup:
                unique_chunks.append(chunk)
        return unique_chunks


class RetrievalCache:
    """In-memory cache for retrieval results with automatic TTL and project invalidation."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._cache: Dict[str, Tuple[float, str, List[Dict[str, Any]]]] = {}
        self._project_keys: Dict[str, Set[str]] = {}
        self.ttl = ttl_seconds

    def _make_key(self, project_id: str, query: str, doc_ids: Optional[List[str]]) -> str:
        doc_str = ",".join(sorted(doc_ids)) if doc_ids else "all"
        raw = f"{project_id}:{query.strip().lower()}:{doc_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, project_id: str, query: str, doc_ids: Optional[List[str]] = None) -> Optional[List[Dict[str, Any]]]:
        settings = get_settings()
        if not settings.ENABLE_RETRIEVAL_CACHE:
            return None

        p_str = str(project_id)
        key = self._make_key(p_str, query, [str(d) for d in doc_ids] if doc_ids else None)
        if key in self._cache:
            ts, pid, val = self._cache[key]
            if time.time() - ts <= self.ttl:
                logger.info(f"Retrieval cache hit for query: '{query}'")
                return [dict(c) for c in val]
            else:
                del self._cache[key]
                if p_str in self._project_keys:
                    self._project_keys[p_str].discard(key)
        return None

    def put(self, project_id: str, query: str, chunks: List[Dict[str, Any]], doc_ids: Optional[List[str]] = None) -> None:
        settings = get_settings()
        if not settings.ENABLE_RETRIEVAL_CACHE:
            return
        p_str = str(project_id)
        key = self._make_key(p_str, query, [str(d) for d in doc_ids] if doc_ids else None)
        self._cache[key] = (time.time(), p_str, [dict(c) for c in chunks])
        if p_str not in self._project_keys:
            self._project_keys[p_str] = set()
        self._project_keys[p_str].add(key)

    def invalidate_project(self, project_id: str) -> None:
        """Invalidate all cached queries belonging to a project."""
        p_str = str(project_id)
        if p_str in self._project_keys:
            for k in self._project_keys[p_str]:
                if k in self._cache:
                    del self._cache[k]
            del self._project_keys[p_str]
        logger.info(f"Invalidated retrieval cache for project {project_id}")


default_retrieval_cache = RetrievalCache()
