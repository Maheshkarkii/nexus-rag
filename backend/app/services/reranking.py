import logging
from typing import Any

from sentence_transformers import CrossEncoder

from app.core.config import get_settings

logger = logging.getLogger("ai_research_assistant.services.reranking")


class RerankingService:
    """Manages the lifecycle of a SentenceTransformers CrossEncoder model for deep semantic relevance scoring."""

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        batch_size: int | None = None,
    ) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.RERANKER_MODEL_NAME
        self.config_device = device or settings.EMBEDDING_DEVICE  # Reuse embedding device setting
        self.batch_size = batch_size or settings.RERANKER_BATCH_SIZE
        self._model: CrossEncoder | None = None
        self._resolved_device: str | None = None

    def _resolve_device(self) -> str:
        """Resolve config device target to a real hardware target (cpu/cuda)."""
        if self._resolved_device is not None:
            return self._resolved_device

        import torch

        device = self.config_device.lower()
        if device == "cuda":
            if not torch.cuda.is_available():
                raise ValueError("CUDA GPU acceleration was explicitly requested, but no GPU was detected by PyTorch.")
            resolved = "cuda"
        elif device == "cpu":
            resolved = "cpu"
        else:  # "auto"
            resolved = "cuda" if torch.cuda.is_available() else "cpu"

        self._resolved_device = resolved
        return resolved

    def load_model(self):
        """Load and cache the CrossEncoder model weights."""
        if self._model is not None:
            return self._model

        from sentence_transformers import CrossEncoder

        device = self._resolve_device()
        logger.info(f"Loading reranker model '{self.model_name}' on device '{device}'...")
        try:
            self._model = CrossEncoder(self.model_name, device=device)
            logger.info(f"Reranker model '{self.model_name}' loaded successfully on '{device}'.")
        except Exception as exc:
            logger.error(f"Failed to load reranker model: {exc}")
            raise RuntimeError(f"Could not load CrossEncoder model: {exc}") from exc

        return self._model

    def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        """Compute cross-encoder relevance scores for (query, chunk_text) pairs and sort candidates descending."""
        if not candidates:
            return []

        # Load model once
        model = self.load_model()

        # Build pairs
        pairs = [(query, c["text"]) for c in candidates]

        try:
            logger.info(f"Rerank predicting {len(pairs)} candidates for query length {len(query)}")
            scores = model.predict(pairs, batch_size=self.batch_size)
            
            if hasattr(scores, "tolist"):
                scores = scores.tolist()
            elif not isinstance(scores, list):
                # Handle single score or float conversion safety
                scores = [float(scores)]

            # Assign scores
            for candidate, score in zip(candidates, scores, strict=False):
                if "vector_score" not in candidate:
                    candidate["vector_score"] = candidate.get("score", 0.0)
                candidate["reranker_score"] = float(score)
                # Primary relevance score is now the reranker score
                candidate["score"] = float(score)

            # Sort descending by reranker score
            candidates.sort(key=lambda x: x["reranker_score"], reverse=True)

            return candidates[:top_k]

        except Exception as exc:
            logger.error(f"Cross-encoder inference failed: {exc}")
            # Fallback strategy: log failure clearly and fallback to vector similarity scores
            logger.warning("Reranking failed. Falling back to default vector similarity scores.")
            for c in candidates:
                c["vector_score"] = c.get("score", 0.0)
                c["reranker_score"] = c.get("score", 0.0)
            candidates.sort(key=lambda x: x["score"], reverse=True)
            return candidates[:top_k]


# Singleton instance
default_reranking_service = RerankingService()


def get_reranking_service() -> RerankingService:
    """Dependency injection target for FastAPI."""
    return default_reranking_service
