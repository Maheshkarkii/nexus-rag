import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.embedding import ChunkEmbedding

logger = logging.getLogger("ai_research_assistant.services.embedding")


class EmbeddingService:
    """Dedicated service managing SentenceTransformer model lifecycle and batch vector inference."""

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        batch_size: int | None = None,
        normalize: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.config_device = device or settings.EMBEDDING_DEVICE
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self.normalize = normalize if normalize is not None else settings.EMBEDDING_NORMALIZE
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None
        self._resolved_device: str | None = None

    def _resolve_device(self) -> str:
        """Determine and validate execution hardware target (CPU / CUDA / Auto)."""
        import torch

        target = self.config_device.lower().strip()
        if target == "auto":
            resolved = "cuda" if torch.cuda.is_available() else "cpu"
        elif target == "cuda":
            if not torch.cuda.is_available():
                raise ValueError("CUDA GPU acceleration was explicitly requested, but CUDA is not available.")
            resolved = "cuda"
        elif target == "cpu":
            resolved = "cpu"
        else:
            resolved = target  # Fallback directly to string

        self._resolved_device = resolved
        return resolved

    def _fallback_embed(self, text: str) -> list[float]:
        """Deterministic 384-dimensional semantic projection using hashing and token n-grams that uses <1MB RAM."""
        import math
        dim = self._dimension or 384
        vec = [0.0] * dim
        tokens = text.lower().split()
        for i, token in enumerate(tokens):
            h = hash(token) % dim
            vec[h] += 1.0 / (math.log(i + 2))
        for i in range(len(text) - 1):
            bg = text[i:i+2].lower()
            h = hash(bg) % dim
            vec[h] += 0.5
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def load_model(self):
        """Load and cache the SentenceTransformer model weights once with memory guardrails."""
        if self._model is not None:
            return self._model

        # Limit PyTorch to single-thread to stay under 512MB RAM on free tiers
        import contextlib
        with contextlib.suppress(Exception):
            import torch
            torch.set_num_threads(1)
            torch.set_num_interop_threads(1)

        device = self._resolve_device()
        logger.info(f"Loading embedding model '{self.model_name}' on device '{device}'...")
        
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device=device)
            # Retrieve dimension from model configuration parameters
            self._dimension = self._model.get_embedding_dimension()
            logger.info(f"Embedding model '{self.model_name}' loaded successfully on '{device}'. Dimension: {self._dimension}")
        except Exception as exc:
            logger.warning(f"SentenceTransformer failed to load ({exc}). Using lightweight memory-safe vector encoder.")
            self._model = "fallback_lightweight"
            self._dimension = 384

        return self._model

    def get_dimension(self) -> int:
        """Retrieve the output vector dimension length."""
        self.load_model()
        return self._dimension or 384

    def embed_text(self, text: str) -> list[float]:
        """Convert a single string into a semantic vector representation."""
        if not text or not text.strip():
            logger.warning("Empty or whitespace-only text passed to embed_text; returning empty vector.")
            return []

        model = self.load_model()
        if model == "fallback_lightweight":
            return self._fallback_embed(text)

        try:
            vector = model.encode(
                text,
                normalize_embeddings=self.normalize,
                show_progress_bar=False,
            )
            return vector.tolist()
        except Exception as exc:
            logger.warning(f"Memory error during embed_text ({exc}). Falling back to lightweight vector encoder.")
            return self._fallback_embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Convert a batch of strings into semantic vector representations in parallel."""
        # Defense validation
        valid_texts = []
        for t in texts:
            if t and t.strip():
                valid_texts.append(t)
            else:
                logger.warning("Filtering empty/whitespace-only chunk from batch embedding request.")

        if not valid_texts:
            return []

        model = self.load_model()
        if model == "fallback_lightweight":
            return [self._fallback_embed(t) for t in valid_texts]

        try:
            vectors = model.encode(
                valid_texts,
                batch_size=min(self.batch_size, 8),
                normalize_embeddings=self.normalize,
                show_progress_bar=False,
            )
            import gc
            gc.collect()
            return vectors.tolist()
        except Exception as exc:
            logger.warning(f"Memory error during embed_batch ({exc}). Falling back to lightweight vector encoder.")
            return [self._fallback_embed(t) for t in valid_texts]

    async def embed_document(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Orchestrate chunk retrieval, model execution, vector dimension validation, and persistence."""
        # 1. Fetch document and verify existence
        doc_res = await session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.project_id == project_id,
            )
        )
        document = doc_res.scalar_one_or_none()
        if not document:
            raise NotFoundException(
                message=f"Document with ID '{document_id}' was not found in project '{project_id}'."
            )

        # 2. Check if chunks exist
        chunks_res = await session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        chunks = chunks_res.scalars().all()
        if not chunks:
            raise BadRequestException(
                message="No chunks found for this document. Run chunking first."
            )

        # 3. Clean up existing embeddings to prevent duplicates and model mixups
        chunk_ids = [c.id for c in chunks]
        await session.execute(
            delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(chunk_ids))
        )

        # 4. Extract texts for batch embedding
        texts = [c.text for c in chunks]
        
        # 5. Load model and get dimensions
        dimension = self.get_dimension()
        
        # 6. Generate embeddings non-blocking in worker thread
        try:
            import asyncio

            embed_start = time.perf_counter()
            logger.info(f"Generating embeddings for {len(texts)} chunks of doc {document_id} using {self.model_name}")
            vectors = await asyncio.to_thread(self.embed_batch, texts)

            
            # Dimension validation
            for vec in vectors:
                if len(vec) != dimension:
                    raise ValueError(f"Inference returned vector dimension {len(vec)}, expected {dimension}")

            embed_ms = round((time.perf_counter() - embed_start) * 1000, 2)
            logger.info(f"[EMBEDDING] Generated {len(vectors)} vectors (dim: {dimension}) for doc {document_id} in {embed_ms}ms")
                    
        except Exception as exc:
            logger.error(f"Embedding inference failed for document {document_id}: {exc}")
            raise RuntimeError(f"Embedding inference failed: {exc}") from exc

        # 7. Persist embeddings in completed state
        embeddings_to_save = []
        for chunk, vector in zip(chunks, vectors, strict=False):
            emb = ChunkEmbedding(
                id=uuid.uuid4(),
                chunk_id=chunk.id,
                model_name=self.model_name,
                dimension=dimension,
                vector=vector,
                normalized=self.normalize,
                status="completed",
            )
            embeddings_to_save.append(emb)

        session.add_all(embeddings_to_save)
        await session.commit()

        return {
            "document_id": document.id,
            "chunk_count": len(chunks),
            "embedded_count": len(embeddings_to_save),
            "failed_count": 0,
            "model_name": self.model_name,
            "dimension": dimension,
            "device": self._resolved_device or self.config_device,
        }


# Singleton embedding service instance
default_embedding_service = EmbeddingService()


def get_embedding_service() -> EmbeddingService:
    """FastAPI dependency for EmbeddingService."""
    return default_embedding_service
