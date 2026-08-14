"""Document processing package exporting processors, normalizers, and service abstractions."""

from app.services.document_processing.base import BaseDocumentProcessor, ExtractionResult
from app.services.document_processing.normalizer import normalize_extracted_text
from app.services.document_processing.service import (
    DocumentProcessingService,
    get_processing_service,
)

__all__ = [
    "BaseDocumentProcessor",
    "ExtractionResult",
    "normalize_extracted_text",
    "DocumentProcessingService",
    "get_processing_service",
]
