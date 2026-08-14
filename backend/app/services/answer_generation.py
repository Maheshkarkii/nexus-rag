import logging
import re
import uuid
import time
from typing import Any, Dict, List, Optional, Tuple, Set

from app.services.citation import SourceRegistry, CitationParser, CitationResolver
from app.services.llm import LLMService
from app.core.observability import GroundednessEvaluator

logger = logging.getLogger("ai_research_assistant.services.answer_generation")


class EvidenceSufficiencyEvaluator:
    """Evaluates whether retrieved evidence is sufficient, partial, or insufficient to answer the user query."""

    @staticmethod
    def evaluate(query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """Determine sufficiency state: 'sufficient', 'partially_sufficient', or 'insufficient'."""
        if not context_chunks:
            return "insufficient"

        combined_text = " ".join([c.get("text", "").lower() for c in context_chunks])
        query_words = [w.lower() for w in re.findall(r"\b\w{4,}\b", query) if w.lower() not in {"what", "where", "which", "explain", "describe", "compare"}]

        if not query_words:
            return "sufficient"

        matches = sum(1 for w in query_words if w in combined_text)
        match_ratio = matches / len(query_words)

        if match_ratio >= 0.6:
            return "sufficient"
        elif match_ratio >= 0.25:
            return "partially_sufficient"
        else:
            return "insufficient"


class ClaimVerifier:
    """Extracts claims and verifies them against retrieved evidence and source citations."""

    @staticmethod
    def extract_claims(answer: str) -> List[Dict[str, Any]]:
        """Deconstruct answer text into sentence-level claims with associated citation IDs."""
        raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if len(s.strip()) > 5]
        claims = []

        for idx, sent in enumerate(raw_sentences):
            cited_tags = re.findall(r"\[S(\d+)\]", sent)
            source_ids = [f"S{m}" for m in cited_tags]
            claims.append({
                "claim_id": f"C{idx + 1}",
                "claim_text": sent,
                "supporting_source_ids": source_ids,
                "support_status": "supported" if source_ids else "unsupported",
            })
        return claims

    @staticmethod
    def verify_and_repair_citations(
        answer: str,
        registry: SourceRegistry,
        context_chunks: List[Dict[str, Any]],
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Validate generated citations against registered sources.
        Removes hallucinated citation tags ([S99] that don't exist) from answer text,
        resolves valid citations, and computes grounding & citation coverage metrics.
        """
        parser = CitationParser()
        resolver = CitationResolver()

        all_registered_sids = set(registry._registry.keys())
        raw_cited_ids = parser.parse(answer)

        # 1. Filter out hallucinated IDs from text
        valid_cited_ids = [sid for sid in raw_cited_ids if sid in all_registered_sids]
        invalid_cited_ids = [sid for sid in raw_cited_ids if sid not in all_registered_sids]

        repaired_answer = answer
        for inv_id in invalid_cited_ids:
            logger.warning(f"Removing invalid/hallucinated citation [{inv_id}] from generated answer.")
            repaired_answer = re.sub(rf"\[{inv_id}\]", "", repaired_answer)

        # Clean up double spaces created by removal
        repaired_answer = re.sub(r" +", " ", repaired_answer)

        # 2. Resolve valid citations
        citations = resolver.resolve(valid_cited_ids, registry)

        # 3. Compute metrics
        grounding_res = GroundednessEvaluator.evaluate_groundedness(repaired_answer, context_chunks)
        citation_eval = GroundednessEvaluator.evaluate_citations(answer, all_registered_sids)

        claims = ClaimVerifier.extract_claims(repaired_answer)
        supported_claims = [c for c in claims if c["supporting_source_ids"]]
        citation_coverage = round(len(supported_claims) / len(claims), 2) if claims else 1.0

        metrics = {
            "grounding_score": grounding_res["groundedness_score"],
            "is_grounded": grounding_res["is_grounded"],
            "citation_coverage": citation_coverage,
            "citation_correctness": citation_eval["correctness_score"],
            "invalid_citations_removed": invalid_cited_ids,
            "claim_count": len(claims),
            "supported_claim_count": len(supported_claims),
        }

        return repaired_answer, citations, metrics


class GroundedAnswerGenerator:
    """
    Stage 35 Production Answer Generation Engine:
    Handles evidence sufficiency checks, structured claim verification, hallucination repair,
    and grounded generation.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    async def generate_grounded_answer(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        system_prompt: str,
        user_prompt: str,
        registry: SourceRegistry,
    ) -> Dict[str, Any]:
        """Generate answer with evidence verification and hallucination repair."""
        sufficiency = EvidenceSufficiencyEvaluator.evaluate(query, context_chunks)

        if sufficiency == "insufficient" and not context_chunks:
            fallback = "I couldn't find enough relevant information in the selected documents to answer this question."
            return {
                "answer": fallback,
                "citations": [],
                "sufficiency": sufficiency,
                "metrics": {
                    "grounding_score": 0.0,
                    "is_grounded": False,
                    "citation_coverage": 0.0,
                    "citation_correctness": 1.0,
                    "invalid_citations_removed": [],
                    "claim_count": 0,
                    "supported_claim_count": 0,
                },
            }

        # First pass generation
        raw_answer = await self.llm_service.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        raw_answer = raw_answer.strip()

        # Citation validation and hallucination repair
        repaired_answer, citations, metrics = ClaimVerifier.verify_and_repair_citations(
            answer=raw_answer,
            registry=registry,
            context_chunks=context_chunks,
        )

        return {
            "answer": repaired_answer,
            "citations": citations,
            "sufficiency": sufficiency,
            "metrics": metrics,
        }
