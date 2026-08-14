"""CSV tabular data extractor converting CSV datasets into structured textual representations."""

import csv
import io
import logging
from pathlib import Path

from app.db.models.document import Document
from app.services.document_processing.base import BaseDocumentProcessor, ExtractionResult

logger = logging.getLogger("ai_research_assistant.processors.csv")


class CSVProcessor(BaseDocumentProcessor):
    """Extracts tabular research datasets from CSV files into structured textual matrices."""

    async def extract(self, file_path: Path, document: Document) -> ExtractionResult:
        if not file_path.exists():
            raise FileNotFoundError(f"Physical CSV file not found at: {file_path}")

        raw_bytes = file_path.read_bytes()
        if not raw_bytes.strip():
            raise ValueError("CSV dataset is empty (0 bytes).")

        # Decode with fallback
        decoded_text = ""
        for enc in ["utf-8-sig", "utf-8", "latin-1"]:
            try:
                decoded_text = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if not decoded_text.strip():
            raise ValueError("CSV dataset could not be decoded or contains only blank content.")

        # Determine delimiter safely
        delimiter = ","
        try:
            sample = decoded_text[:2048]
            dialect = csv.Sniffer().sniff(sample)
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ","

        reader = csv.reader(io.StringIO(decoded_text), delimiter=delimiter)
        rows: list[list[str]] = [row for row in reader if any(cell.strip() for cell in row)]

        if not rows:
            raise ValueError("CSV document contains no tabular rows or columns.")

        header = rows[0]
        data_rows = rows[1:]

        output_lines: list[str] = [
            f"Columns: {' | '.join(header)}",
            "",
        ]

        for idx, row in enumerate(data_rows, start=1):
            formatted_row = " | ".join(cell.strip() for cell in row)
            output_lines.append(f"Row {idx}: {formatted_row}")

        combined_text = "\n".join(output_lines).strip()
        char_count = len(combined_text)
        word_count = len(combined_text.split())

        return ExtractionResult(
            text=combined_text,
            character_count=char_count,
            word_count=word_count,
            metadata={
                "column_names": header,
                "column_count": len(header),
                "row_count": len(data_rows),
                "delimiter": delimiter,
            },
        )
