"""JSON document extractor converting structured JSON data into readable hierarchical text."""

import json
import logging
from pathlib import Path
from typing import Any

from app.db.models.document import Document
from app.services.document_processing.base import BaseDocumentProcessor, ExtractionResult

logger = logging.getLogger("ai_research_assistant.processors.json")


def format_json_hierarchy(data: Any, indent_level: int = 0) -> list[str]:
    """Recursively convert nested JSON structures into deterministic human-readable text."""
    prefix = "  " * indent_level
    lines: list[str] = []

    if isinstance(data, dict):
        if not data:
            lines.append(f"{prefix}(empty object)")
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(format_json_hierarchy(value, indent_level + 1))
            else:
                lines.append(f"{prefix}{key}: {value}")
    elif isinstance(data, list):
        if not data:
            lines.append(f"{prefix}(empty list)")
        for idx, item in enumerate(data, start=1):
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}- Item {idx}:")
                lines.extend(format_json_hierarchy(item, indent_level + 1))
            else:
                lines.append(f"{prefix}- {item}")
    else:
        lines.append(f"{prefix}{data}")

    return lines


class JSONProcessor(BaseDocumentProcessor):
    """Extracts structured hierarchical textual representations from JSON dataset files."""

    async def extract(self, file_path: Path, document: Document) -> ExtractionResult:
        if not file_path.exists():
            raise FileNotFoundError(f"Physical JSON file not found at: {file_path}")

        raw_bytes = file_path.read_bytes()
        if not raw_bytes.strip():
            raise ValueError("JSON file is empty (0 bytes).")

        try:
            parsed_data = json.loads(raw_bytes.decode("utf-8-sig"))
        except Exception as e:
            try:
                parsed_data = json.loads(raw_bytes.decode("latin-1"))
            except Exception as inner_e:
                raise ValueError(f"Failed to parse invalid JSON document: {inner_e}") from e

        formatted_lines = format_json_hierarchy(parsed_data)
        combined_text = "\n".join(formatted_lines).strip()

        if not combined_text:
            raise ValueError("JSON document contains no extractable keys, arrays, or primitive values.")

        char_count = len(combined_text)
        word_count = len(combined_text.split())

        item_count = len(parsed_data) if isinstance(parsed_data, (dict, list)) else 1

        return ExtractionResult(
            text=combined_text,
            character_count=char_count,
            word_count=word_count,
            metadata={
                "root_type": type(parsed_data).__name__,
                "item_count": item_count,
            },
        )
