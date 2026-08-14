"""PDF text and structure extractor using pypdf."""

import logging
from pathlib import Path
from typing import List
from pypdf import PdfReader
from app.db.models.document import Document
from app.services.document_processing.base import BaseDocumentProcessor, ExtractionResult

logger = logging.getLogger("ai_research_assistant.processors.pdf")


class PDFProcessor(BaseDocumentProcessor):
    """Extracts text page-by-page from PDF documents, preserving page boundaries for citations."""

    async def extract(self, file_path: Path, document: Document) -> ExtractionResult:
        if not file_path.exists():
            raise FileNotFoundError(f"Physical PDF file not found at: {file_path}")

        try:
            reader = PdfReader(str(file_path))
        except Exception as e:
            raise ValueError(f"Failed to parse PDF document structure: {e}") from e

        total_pages = len(reader.pages)
        if total_pages == 0:
            raise ValueError("PDF document contains 0 pages.")

        page_texts: List[str] = []
        page_metadata = []
        warnings = []

        for idx, page in enumerate(reader.pages, start=1):
            try:
                raw_page_text = page.extract_text() or ""
            except Exception as page_err:
                logger.warning(f"Error extracting text from page {idx} of doc {document.id}: {page_err}")
                raw_page_text = ""
                warnings.append(f"Page {idx}: Extraction failed ({page_err})")

            cleaned = raw_page_text.strip()
            if cleaned:
                page_texts.append(f"--- Page {idx} ---\n{cleaned}")
                page_metadata.append({
                    "page_number": idx,
                    "character_count": len(cleaned),
                    "word_count": len(cleaned.split()),
                })
            else:
                page_metadata.append({
                    "page_number": idx,
                    "character_count": 0,
                    "word_count": 0,
                })

        combined_text = "\n\n".join(page_texts).strip()

        if not combined_text:
            raise ValueError(
                "No extractable text found in PDF document. "
                "Scanned documents or image-only PDFs without digital text layers are not currently supported."
            )

        char_count = len(combined_text)
        word_count = len(combined_text.split())

        return ExtractionResult(
            text=combined_text,
            character_count=char_count,
            word_count=word_count,
            page_count=total_pages,
            metadata={
                "page_count": total_pages,
                "pages_with_text": len(page_texts),
                "pages": page_metadata,
            },
            warnings=warnings,
        )
