import logging
import re
import uuid
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("ai_research_assistant.multimodal_intelligence")


# --- Document Element Schema ---

class DocumentElement(BaseModel):
    element_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    element_type: str  # text, heading, table, figure, caption, sheet, dataset
    document_id: str
    page_number: int | None = None
    section_title: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Multimodal Extractors ---

class TableExtractor:
    """Extracts, structures, and formats tables from document text/PDFs."""

    @staticmethod
    def extract_tables(raw_text: str, document_id: str) -> list[DocumentElement]:
        elements = []
        # Pattern to detect markdown/ASCII tables
        table_pattern = r"(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)"
        matches = re.finditer(table_pattern, raw_text)

        for idx, match in enumerate(matches):
            tbl_text = match.group(1).strip()
            elements.append(
                DocumentElement(
                    element_type="table",
                    document_id=document_id,
                    content=tbl_text,
                    metadata={
                        "table_id": f"table_{idx+1}",
                        "is_structured_table": True,
                        "row_count": len(tbl_text.splitlines()) - 2,
                    },
                )
            )
        return elements


class FigureExtractor:
    """Detects figure references, captions, and visual chart metadata."""

    @staticmethod
    def extract_figures(raw_text: str, document_id: str) -> list[DocumentElement]:
        elements = []
        # Pattern to detect Figure captions (e.g. Figure 1: Accuracy comparison)
        fig_pattern = r"(Figure\s+\d+[:\s][^\n]+)"
        matches = re.finditer(fig_pattern, raw_text, re.IGNORECASE)

        for idx, match in enumerate(matches):
            caption = match.group(1).strip()
            elements.append(
                DocumentElement(
                    element_type="figure",
                    document_id=document_id,
                    content=caption,
                    metadata={
                        "figure_id": f"fig_{idx+1}",
                        "caption": caption,
                        "is_visual_element": True,
                    },
                )
            )
        return elements


class SpreadsheetExtractor:
    """Extracts structured sheet and dataset schema metadata."""

    @staticmethod
    def extract_sheets(metadata: dict[str, Any], document_id: str) -> list[DocumentElement]:
        elements = []
        filename = metadata.get("source_filename", "dataset")
        sheets = metadata.get("sheets", [])

        for s in sheets:
            sheet_name = s.get("sheet_name", "Sheet1")
            content = f"Spreadsheet Workbook '{filename}' | Sheet: '{sheet_name}' | Rows: {s.get('row_count')} | Columns: {s.get('column_count')}"
            elements.append(
                DocumentElement(
                    element_type="sheet",
                    document_id=document_id,
                    content=content,
                    metadata={
                        "sheet_name": sheet_name,
                        "row_count": s.get("row_count"),
                        "column_count": s.get("column_count"),
                    },
                )
            )
        return elements


# --- Document Intelligence Pipeline ---

class DocumentIntelligenceEngine:
    """Transforms raw documents into rich multimodal document elements."""

    @classmethod
    def process_document(
        cls,
        document_id: str,
        raw_text: str,
        extracted_metadata: dict[str, Any] | None = None,
    ) -> list[DocumentElement]:
        metadata = extracted_metadata or {}
        elements: list[DocumentElement] = []

        # 1. Extract Headings & Text Blocks
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        for idx, p in enumerate(paragraphs):
            if p.startswith("#") or (len(p) < 80 and p.isupper()):
                elements.append(
                    DocumentElement(
                        element_type="heading",
                        document_id=document_id,
                        content=p,
                        metadata={"heading_level": p.count("#") or 1},
                    )
                )
            else:
                elements.append(
                    DocumentElement(
                        element_type="text",
                        document_id=document_id,
                        content=p,
                        metadata={"paragraph_index": idx},
                    )
                )

        # 2. Extract Tables
        tables = TableExtractor.extract_tables(raw_text, document_id)
        elements.extend(tables)

        # 3. Extract Figures
        figures = FigureExtractor.extract_figures(raw_text, document_id)
        elements.extend(figures)

        # 4. Extract Spreadsheet Sheets
        if "sheets" in metadata:
            sheets = SpreadsheetExtractor.extract_sheets(metadata, document_id)
            elements.extend(sheets)

        return elements


document_intelligence_engine = DocumentIntelligenceEngine()
