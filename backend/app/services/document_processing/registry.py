"""Processor registry mapping document formats and extensions to dedicated extractors."""


from app.db.models.document import Document
from app.services.document_processing.base import BaseDocumentProcessor
from app.services.document_processing.csv_processor import CSVProcessor
from app.services.document_processing.docx_processor import DocxProcessor
from app.services.document_processing.excel_processor import ExcelProcessor
from app.services.document_processing.json_processor import JSONProcessor
from app.services.document_processing.pdf_processor import PDFProcessor
from app.services.document_processing.text_processor import TextProcessor

# Singleton processor instances
_pdf_processor = PDFProcessor()
_docx_processor = DocxProcessor()
_text_processor = TextProcessor()
_csv_processor = CSVProcessor()
_excel_processor = ExcelProcessor()
_json_processor = JSONProcessor()

# Extension to processor mapping (lower-case with dot)
EXTENSION_PROCESSORS: dict[str, BaseDocumentProcessor] = {
    ".pdf": _pdf_processor,
    ".docx": _docx_processor,
    ".txt": _text_processor,
    ".csv": _csv_processor,
    ".xlsx": _excel_processor,
    ".xls": _excel_processor,
    ".json": _json_processor,
}

# MIME type fallback mapping
MIME_PROCESSORS: dict[str, BaseDocumentProcessor] = {
    "application/pdf": _pdf_processor,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": _docx_processor,
    "application/msword": _docx_processor,
    "text/plain": _text_processor,
    "text/csv": _csv_processor,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": _excel_processor,
    "application/vnd.ms-excel": _excel_processor,
    "application/json": _json_processor,
}


def get_processor_for_document(document: Document) -> BaseDocumentProcessor:
    """Resolve the appropriate processor instance based on extension and MIME type."""
    ext = (document.file_extension or "").lower().strip()
    if ext in EXTENSION_PROCESSORS:
        return EXTENSION_PROCESSORS[ext]

    mime = (document.mime_type or "").lower().strip()
    if mime in MIME_PROCESSORS:
        return MIME_PROCESSORS[mime]

    raise ValueError(
        f"No processor registered for file extension '{ext}' or MIME type '{mime}'."
    )
