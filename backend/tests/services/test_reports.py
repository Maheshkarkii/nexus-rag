import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.db.models.report import Report
from app.services.export_adapters import MarkdownExporter, PDFExporter, DOCXExporter
from app.services.report_generator import ReportGeneratorService
from app.services.retrieval_pipeline import RetrievalPipeline
from app.services.prompt_builder import PromptBuilder


def test_markdown_exporter() -> None:
    content_json = {
        "title": "Sample Research Report",
        "report_type": "comparative_report",
        "sections": [
            {"title": "Executive Summary", "content": "This paper analyzes AI algorithms [S1]."},
            {"title": "Methodology", "content": "Compared model architectures [S2]."}
        ],
        "sources": [
            {"source_id": "S1", "filename": "paper_a.pdf", "location_info": "Page 3"},
            {"source_id": "S2", "filename": "paper_b.pdf", "location_info": "Page 5"}
        ]
    }

    md = MarkdownExporter.export(content_json)
    assert "# Sample Research Report" in md
    assert "## Executive Summary" in md
    assert "## Sources" in md
    assert "1. **[S1]** paper_a.pdf (Page 3)" in md


def test_pdf_exporter() -> None:
    content_json = {
        "title": "PDF Test Report",
        "report_type": "research_summary",
        "sections": [{"title": "Overview", "content": "PDF generation testing."}],
        "sources": [{"source_id": "S1", "filename": "doc.pdf", "location_info": "Page 1"}]
    }

    pdf_bytes = PDFExporter.export(content_json)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")


def test_docx_exporter() -> None:
    content_json = {
        "title": "DOCX Test Report",
        "report_type": "research_summary",
        "sections": [{"title": "Overview", "content": "DOCX generation testing."}],
        "sources": [{"source_id": "S1", "filename": "doc.pdf", "location_info": "Page 1"}]
    }

    docx_bytes = DOCXExporter.export(content_json)
    assert isinstance(docx_bytes, bytes)
    assert docx_bytes.startswith(b"PK\x03\x04")


@pytest.mark.asyncio
async def test_report_generator_invalid_citation_sanitization(db_session: AsyncSession) -> None:
    project = Project(id=uuid.uuid4(), name="Report Test Workspace")
    db_session.add(project)
    await db_session.commit()

    mock_llm = AsyncMock()
    # Mock LLM generates text containing a valid citation [S1] and an invalid hallucinated citation [S99]
    mock_llm.generate.return_value = "The model achieved 95% accuracy [S1] but other papers report lower [S99]."

    mock_retrieval_svc = AsyncMock()
    mock_retrieval_svc.retrieve.return_value = [
        {"chunk_id": uuid.uuid4(), "document_id": uuid.uuid4(), "project_id": project.id, "text": "Model accuracy is 95%", "score": 0.95, "metadata": {"source_filename": "paper_a.pdf", "page_number": 2}}
    ]

    mock_rerank_svc = MagicMock()
    mock_rerank_svc.rerank.side_effect = lambda query=None, candidates=None, top_k=None, **kwargs: candidates

    generator = ReportGeneratorService(
        llm_service=mock_llm,
        retrieval_pipeline=RetrievalPipeline(),
        retrieval_service=mock_retrieval_svc,
        reranking_service=mock_rerank_svc,
        qdrant_service=MagicMock(),
        embedding_service=MagicMock(),
        prompt_builder=PromptBuilder(),
    )

    report = await generator.generate_report(
        session=db_session,
        project_id=project.id,
        report_type="research_summary",
    )

    assert report.status == "completed"
    assert report.version == 1
    assert report.content_json is not None
    
    # Check that [S1] is preserved and invalid [S99] tag was sanitized/removed
    sec_content = report.content_json["sections"][0]["content"]
    assert "[S1]" in sec_content
    assert "[S99]" not in sec_content
