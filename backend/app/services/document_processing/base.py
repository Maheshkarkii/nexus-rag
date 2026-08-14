"""Base classes, data models, and contracts for document text extraction processors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.db.models.document import Document


@dataclass
class ExtractionResult:
    """Normalized output produced by a document processor ready for downstream chunking."""

    text: str
    character_count: int
    word_count: int
    page_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class BaseDocumentProcessor(ABC):
    """Abstract base class for all file-format-specific document extractors."""

    @abstractmethod
    async def extract(self, file_path: Path, document: Document) -> ExtractionResult:
        """Extract structured textual content and metadata from the physical file."""
        pass
