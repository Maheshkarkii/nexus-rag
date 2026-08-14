"""Plain text document extractor supporting multiple common text encodings."""

import logging
from pathlib import Path

from app.db.models.document import Document
from app.services.document_processing.base import BaseDocumentProcessor, ExtractionResult

logger = logging.getLogger("ai_research_assistant.processors.text")

SUPPORTED_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]


class TextProcessor(BaseDocumentProcessor):
    """Extracts and normalizes text from plain text (.txt) research notes and transcripts."""

    async def extract(self, file_path: Path, document: Document) -> ExtractionResult:
        if not file_path.exists():
            raise FileNotFoundError(f"Physical text file not found at: {file_path}")

        raw_bytes = file_path.read_bytes()
        if not raw_bytes:
            raise ValueError("Text document is completely empty (0 bytes).")

        decoded_text: str = ""
        successful_encoding: str = "utf-8"

        for enc in SUPPORTED_ENCODINGS:
            try:
                decoded_text = raw_bytes.decode(enc)
                successful_encoding = enc
                break
            except UnicodeDecodeError:
                continue

        if not decoded_text.strip():
            raise ValueError("Text document contains only blank or unreadable whitespace content.")

        lines = decoded_text.splitlines()
        char_count = len(decoded_text)
        word_count = len(decoded_text.split())

        return ExtractionResult(
            text=decoded_text,
            character_count=char_count,
            word_count=word_count,
            metadata={
                "line_count": len(lines),
                "encoding": successful_encoding,
            },
        )
