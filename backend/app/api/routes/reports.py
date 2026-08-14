import uuid
import json
import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models.report import Report
from app.db.models.project import Project
from app.services.llm import get_llm_service, LLMService
from app.services.retrieval_pipeline import RetrievalPipeline
from app.services.retrieval import get_retrieval_service, RetrievalService
from app.services.reranking import get_reranking_service, RerankingService
from app.services.qdrant import get_qdrant_service, QdrantService
from app.services.embedding import get_embedding_service, EmbeddingService
from app.services.prompt_builder import default_prompt_builder, PromptBuilder
from app.services.report_generator import ReportGeneratorService
from app.services.export_adapters import MarkdownExporter, PDFExporter, DOCXExporter

router = APIRouter(tags=["Reports"])


class GenerateReportRequest(BaseModel):
    report_type: str = Field(default="research_summary", description="Type of report to generate")
    query: Optional[str] = Field(default=None, description="Optional custom research query/objective")
    conversation_id: Optional[uuid.UUID] = Field(default=None, description="Associated research conversation ID")
    document_ids: Optional[List[uuid.UUID]] = Field(default=None, description="Optional document scope list")


from pydantic import BaseModel, Field, ConfigDict

class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    conversation_id: Optional[uuid.UUID]
    title: str
    report_type: str
    status: str
    version: int
    content_json: Optional[Dict[str, Any]]
    created_at: Any


def get_report_generator_service(
    llm_service: LLMService = Depends(get_llm_service),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    reranking_service: RerankingService = Depends(get_reranking_service),
    qdrant_service: QdrantService = Depends(get_qdrant_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> ReportGeneratorService:
    return ReportGeneratorService(
        llm_service=llm_service,
        retrieval_pipeline=RetrievalPipeline(),
        retrieval_service=retrieval_service,
        reranking_service=reranking_service,
        qdrant_service=qdrant_service,
        embedding_service=embedding_service,
        prompt_builder=default_prompt_builder,
    )


@router.post(
    "/projects/{project_id}/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a research report",
)
async def generate_report(
    project_id: uuid.UUID,
    payload: GenerateReportRequest,
    db: AsyncSession = Depends(get_db),
    generator: ReportGeneratorService = Depends(get_report_generator_service),
):
    """Generate a structured, grounded research report."""
    report = await generator.generate_report(
        session=db,
        project_id=project_id,
        report_type=payload.report_type,
        query=payload.query,
        conversation_id=payload.conversation_id,
        document_ids=payload.document_ids,
        is_streaming=False,
    )
    return report


@router.post(
    "/projects/{project_id}/reports/stream",
    summary="Stream research report generation progress events",
)
async def stream_report_generation(
    project_id: uuid.UUID,
    payload: GenerateReportRequest,
    db: AsyncSession = Depends(get_db),
    generator: ReportGeneratorService = Depends(get_report_generator_service),
):
    """Stream report generation progress using Server-Sent Events (SSE)."""
    event_queue = asyncio.Queue()

    async def generate_task():
        try:
            await generator.generate_report(
                session=db,
                project_id=project_id,
                report_type=payload.report_type,
                query=payload.query,
                conversation_id=payload.conversation_id,
                document_ids=payload.document_ids,
                is_streaming=True,
                event_queue=event_queue,
            )
        except Exception as e:
            await event_queue.put({"type": "error", "data": {"message": str(e)}})
        finally:
            await event_queue.put(None)

    asyncio.create_task(generate_task())

    async def event_generator():
        while True:
            event = await event_queue.get()
            if event is None:
                break
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get(
    "/projects/{project_id}/reports",
    response_model=List[ReportResponse],
    summary="List project research reports",
)
async def list_reports(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all reports belonging to a research project workspace."""
    stmt = select(Report).where(Report.project_id == project_id).order_by(Report.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get(
    "/projects/{project_id}/reports/{report_id}",
    response_model=ReportResponse,
    summary="Retrieve report details",
)
async def get_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details and structured JSON content for a specific report."""
    stmt = select(Report).where(Report.id == report_id, Report.project_id == project_id)
    res = await db.execute(stmt)
    report = res.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@router.delete(
    "/projects/{project_id}/reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete research report",
)
async def delete_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a research report."""
    stmt = select(Report).where(Report.id == report_id, Report.project_id == project_id)
    res = await db.execute(stmt)
    report = res.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    await db.delete(report)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/projects/{project_id}/reports/{report_id}/export/{format}",
    summary="Export report file (markdown, pdf, docx)",
)
async def export_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    format: str,
    db: AsyncSession = Depends(get_db),
):
    """Export a structured research report into Markdown, PDF, or DOCX formats."""
    stmt = select(Report).where(Report.id == report_id, Report.project_id == project_id)
    res = await db.execute(stmt)
    report = res.scalar_one_or_none()
    if not report or not report.content_json:
        raise HTTPException(status_code=404, detail="Report or report content not found.")

    fmt = format.lower()
    title_slug = report.title.lower().replace(" ", "_")

    if fmt == "markdown" or fmt == "md":
        md_text = MarkdownExporter.export(report.content_json)
        return Response(
            content=md_text,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{title_slug}_v{report.version}.md"'},
        )
    elif fmt == "pdf":
        pdf_bytes = PDFExporter.export(report.content_json)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{title_slug}_v{report.version}.pdf"'},
        )
    elif fmt == "docx":
        docx_bytes = DOCXExporter.export(report.content_json)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{title_slug}_v{report.version}.docx"'},
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format. Supported formats: markdown, pdf, docx.")
