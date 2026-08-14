import uuid
import pytest

from app.services.document_processing.multimodal_intelligence import (
    DocumentIntelligenceEngine,
    TableExtractor,
    FigureExtractor,
    SpreadsheetExtractor,
)


def test_table_extraction() -> None:
    doc_id = str(uuid.uuid4())
    sample_text = (
        "Here is the experimental result table:\n\n"
        "| Model | Accuracy | F1-Score |\n"
        "|---|---|---|\n"
        "| ResNet-50 | 93.4% | 0.91 |\n"
        "| BERT-large | 94.2% | 0.93 |\n"
    )

    tables = TableExtractor.extract_tables(sample_text, doc_id)
    assert len(tables) == 1
    assert tables[0].element_type == "table"
    assert tables[0].metadata["table_id"] == "table_1"
    assert tables[0].metadata["row_count"] == 2


def test_figure_extraction() -> None:
    doc_id = str(uuid.uuid4())
    sample_text = (
        "The model architecture is illustrated below.\n\n"
        "Figure 1: Overall architectural overview of the RAG system."
    )

    figures = FigureExtractor.extract_figures(sample_text, doc_id)
    assert len(figures) == 1
    assert figures[0].element_type == "figure"
    assert figures[0].metadata["figure_id"] == "fig_1"
    assert "Figure 1:" in figures[0].content


def test_spreadsheet_extraction() -> None:
    doc_id = str(uuid.uuid4())
    meta = {
        "source_filename": "financial_q3.xlsx",
        "sheets": [
            {"sheet_name": "Revenue", "row_count": 120, "column_count": 8},
            {"sheet_name": "Expenses", "row_count": 95, "column_count": 6},
        ],
    }

    sheets = SpreadsheetExtractor.extract_sheets(meta, doc_id)
    assert len(sheets) == 2
    assert sheets[0].element_type == "sheet"
    assert sheets[0].metadata["sheet_name"] == "Revenue"


def test_document_intelligence_processing() -> None:
    doc_id = str(uuid.uuid4())
    raw_doc = (
        "# Introduction\n\n"
        "This paper presents novel neural network architectures.\n\n"
        "Figure 2: Training loss convergence curve across epochs.\n\n"
        "| Epoch | Loss |\n"
        "|---|---|\n"
        "| 1 | 0.45 |\n"
    )

    elements = DocumentIntelligenceEngine.process_document(doc_id, raw_doc)
    types = {e.element_type for e in elements}

    assert "heading" in types
    assert "text" in types
    assert "table" in types
    assert "figure" in types
