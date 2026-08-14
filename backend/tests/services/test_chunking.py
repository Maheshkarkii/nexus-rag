import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.project import Project
from app.services.document_processing.chunking.recursive import RecursiveChunkingStrategy, count_tokens
from app.services.document_processing.chunking.structural import (
    PDFChunkingStrategy,
    DocxChunkingStrategy,
    CSVChunkingStrategy,
    ExcelChunkingStrategy,
    JSONChunkingStrategy,
)
from app.services.document_processing.chunking.service import ChunkingService


def create_mock_doc(ext: str, text: str = "") -> Document:
    """Helper to create a mock Document."""
    return Document(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        original_filename=f"test{ext}",
        stored_filename=f"{uuid.uuid4().hex}{ext}",
        storage_path=f"projects/mock/test{ext}",
        mime_type="application/octet-stream",
        file_extension=ext,
        file_size=1024,
        status="ready" if text else "uploaded",
        extracted_text=text,
        extracted_character_count=len(text) if text else None,
    )


# ------------------------------------------------------------------------------
# 1. Token Counting Unit Tests
# ------------------------------------------------------------------------------
def test_count_tokens() -> None:
    assert count_tokens("") == 0
    assert count_tokens("hello") == 1
    assert count_tokens("a" * 400) == 100


# ------------------------------------------------------------------------------
# 2. Recursive Chunking Unit Tests
# ------------------------------------------------------------------------------
def test_recursive_chunking_small_text() -> None:
    strategy = RecursiveChunkingStrategy()
    doc = create_mock_doc(".txt")
    text = "Short text."
    chunks = strategy.chunk(text, doc, chunk_size=50, chunk_overlap=10)
    assert len(chunks) == 1
    assert chunks[0]["text"] == "Short text."


def test_recursive_chunking_large_paragraphs() -> None:
    strategy = RecursiveChunkingStrategy()
    doc = create_mock_doc(".txt")
    text = "This is paragraph one.\n\nThis is paragraph two. It is slightly longer and contains more details."
    chunks = strategy.chunk(text, doc, chunk_size=40, chunk_overlap=10)
    assert len(chunks) > 1
    # Check that sentences or paragraphs are not arbitrarily split where avoidable
    for c in chunks:
        assert len(c["text"]) <= 40


def test_recursive_chunking_sentence_boundaries() -> None:
    strategy = RecursiveChunkingStrategy()
    doc = create_mock_doc(".txt")
    text = "Sentence one. Sentence two. Sentence three."
    chunks = strategy.chunk(text, doc, chunk_size=30, chunk_overlap=5)
    assert len(chunks) >= 2
    # Ensure they split near punctuation
    assert "Sentence one." in chunks[0]["text"]


def test_recursive_chunking_overlap() -> None:
    strategy = RecursiveChunkingStrategy()
    doc = create_mock_doc(".txt")
    text = "WordA WordB WordC WordD WordE"
    # Low size to force splits
    chunks = strategy.chunk(text, doc, chunk_size=15, chunk_overlap=6)
    assert len(chunks) > 1


# ------------------------------------------------------------------------------
# 3. Structural Chunking Unit Tests
# ------------------------------------------------------------------------------
def test_pdf_chunking_page_metadata() -> None:
    strategy = PDFChunkingStrategy()
    doc = create_mock_doc(".pdf")
    text = "--- Page 1 ---\nThis is page one text.\n\n--- Page 2 ---\nThis is page two text."
    chunks = strategy.chunk(text, doc, chunk_size=100, chunk_overlap=10)
    assert len(chunks) == 2
    assert chunks[0]["metadata"]["page_number"] == 1
    assert chunks[1]["metadata"]["page_number"] == 2


def test_docx_chunking_section_metadata() -> None:
    strategy = DocxChunkingStrategy()
    doc = create_mock_doc(".docx")
    text = "## Introduction\nWelcome to the doc.\n\n## Section 2\nSome methodology details."
    chunks = strategy.chunk(text, doc, chunk_size=100, chunk_overlap=10)
    assert len(chunks) == 2
    assert chunks[0]["metadata"]["section_title"] == "Introduction"
    assert chunks[0]["metadata"]["section_path"] == "Introduction"
    assert chunks[1]["metadata"]["section_title"] == "Section 2"
    assert chunks[1]["metadata"]["section_path"] == "Section 2"


def test_csv_chunking_row_ranges() -> None:
    strategy = CSVChunkingStrategy()
    doc = create_mock_doc(".csv")
    text = "Columns: name | role | salary\nRow 1: Alice | Dev | 100\nRow 2: Bob | PM | 120"
    chunks = strategy.chunk(text, doc, chunk_size=150, chunk_overlap=10)
    assert len(chunks) == 1
    assert chunks[0]["metadata"]["column_names"] == ["name", "role", "salary"]
    assert chunks[0]["metadata"]["row_start"] == 1
    assert chunks[0]["metadata"]["row_end"] == 2


def test_excel_chunking_sheet_boundaries() -> None:
    strategy = ExcelChunkingStrategy()
    doc = create_mock_doc(".xlsx")
    text = (
        "Sheet: Sales\nColumns: month | revenue\nRow 1: Jan | 10k\n\n"
        "---\n\n"
        "Sheet: Costs\nColumns: month | cost\nRow 1: Jan | 5k"
    )
    chunks = strategy.chunk(text, doc, chunk_size=150, chunk_overlap=10)
    assert len(chunks) == 2
    assert chunks[0]["metadata"]["sheet_name"] == "Sales"
    assert chunks[1]["metadata"]["sheet_name"] == "Costs"


def test_json_chunking_hierarchy_metadata() -> None:
    strategy = JSONChunkingStrategy()
    doc = create_mock_doc(".json")
    text = (
        "users:\n"
        "  - Item 1:\n"
        "      name: Alice\n"
        "      role: Dev\n"
        "  - Item 2:\n"
        "      name: Bob\n"
        "      role: PM"
    )
    chunks = strategy.chunk(text, doc, chunk_size=40, chunk_overlap=10)
    assert len(chunks) > 0
    assert "json_path" in chunks[0]["metadata"]
    assert chunks[0]["metadata"]["json_path"].startswith("root")


# ------------------------------------------------------------------------------
# 4. Service Reprocessing Integration Tests
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chunking_service_reprocessing_lifecycle(db_session: AsyncSession) -> None:
    # 1. Set up a project and document in database
    project = Project(id=uuid.uuid4(), name="Test Project", description="Test Desc")
    db_session.add(project)
    await db_session.commit()

    document = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="manual.txt",
        stored_filename="manual_stored.txt",
        storage_path="projects/test/manual.txt",
        mime_type="text/plain",
        file_extension=".txt",
        file_size=1024,
        status="ready",
        extracted_text="Paragraph A.\n\nParagraph B.\n\nParagraph C.",
        extracted_character_count=36,
    )
    db_session.add(document)
    await db_session.commit()

    service = ChunkingService()

    # 2. Chunk document first time
    res = await service.chunk_document(
        session=db_session,
        project_id=project.id,
        document_id=document.id,
        chunk_size=20,
        chunk_overlap=5,
    )

    assert res["chunk_count"] > 0
    assert res["total_characters"] > 0
    assert res["total_tokens"] > 0

    # Verify database has chunks
    chunks_stmt = select(DocumentChunk).where(DocumentChunk.document_id == document.id)
    chunks_res = await db_session.execute(chunks_stmt)
    chunks = chunks_res.scalars().all()
    first_chunk_count = len(chunks)
    assert first_chunk_count == res["chunk_count"]
    for c in chunks:
        assert c.document_id == document.id
        assert c.project_id == project.id
        assert c.chunk_index is not None
        assert c.text
        assert c.token_count > 0
        assert c.character_count > 0
        assert c.metadata_["source_filename"] == "manual.txt"

    # 3. Reprocess document with different size parameters
    res2 = await service.chunk_document(
        session=db_session,
        project_id=project.id,
        document_id=document.id,
        chunk_size=100,  # much larger -> fewer chunks
        chunk_overlap=5,
    )

    # Verify old chunks were replaced, and not appended/duplicated
    chunks_res2 = await db_session.execute(chunks_stmt)
    chunks2 = chunks_res2.scalars().all()
    assert len(chunks2) == res2["chunk_count"]
    assert len(chunks2) < first_chunk_count
