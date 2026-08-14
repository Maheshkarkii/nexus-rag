import abc
from typing import List, Dict, Any
from app.db.models.document import Document

class ChunkingStrategy(abc.ABC):
    """Abstract base class for all chunking strategies."""

    @abc.abstractmethod
    def chunk(self, text: str, document: Document, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        """
        Partition document text into smaller, contextual chunks.

        Args:
            text: Normalized document text.
            document: Parent document model for context.
            chunk_size: Maximum chunk size (typically characters or tokens).
            chunk_overlap: Overlap between consecutive chunks.

        Returns:
            A list of dictionaries representing the generated chunks, each containing:
            - "text": The chunk text.
            - "metadata": Format-specific metadata dict.
        """
        pass
