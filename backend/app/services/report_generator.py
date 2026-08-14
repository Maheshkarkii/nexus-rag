import logging
import uuid
import re
import json
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import get_settings
from app.db.models.report import Report
from app.db.models.project import Project
from app.db.models.conversation import Conversation
from app.services.llm import LLMService
from app.services.retrieval_pipeline import RetrievalPipeline
from app.services.retrieval import RetrievalService
from app.services.reranking import RerankingService
from app.services.qdrant import QdrantService
from app.services.embedding import EmbeddingService
from app.services.prompt_builder import PromptBuilder
from app.services.citation import SourceRegistry, CitationParser, CitationResolver
from app.services.research import ResearchOrchestrator
from app.core.exceptions import NotFoundException, BadRequestException

logger = logging.getLogger("ai_research_assistant.services.report_generator")


class ReportGeneratorService:
    """Orchestrates structured research report generation, section-by-section evidence mapping, citation validation, and versioning."""

    REPORT_TEMPLATES = {
        "research_summary": [
            ("Executive Summary", "Summarize overall research goals and main findings."),
            ("Key Research Findings", "Detail evidence-backed findings."),
            ("Limitations & Uncertainties", "Highlight missing context and document limitations."),
            ("Conclusion", "Provide high-level takeaway."),
            ("References", "List verified source citations."),
        ],
        "literature_review": [
            ("Introduction & Research Scope", "Outline research themes and document scope."),
            ("Major Research Themes", "Group findings into key thematic pillars."),
            ("Methodological Trends & Patterns", "Analyze common methodologies and techniques across sources."),
            ("Agreements & Disagreements", "Contrast consensus points and conflicting findings across literature."),
            ("Identified Gaps & Limitations", "Report documented research gaps or limitations."),
            ("Conclusion", "Synthesize overall state of research."),
            ("References", "List verified source citations."),
        ],
        "technical_report": [
            ("Executive Summary", "High-level summary of technical specifications and findings."),
            ("Introduction & Problem Statement", "Define technical objectives and problem space."),
            ("Methodology & Implementation Details", "Explain architectures, data formats, and methods."),
            ("Technical Findings & Results", "Present evidence-backed technical evaluations and findings."),
            ("Limitations & Edge Cases", "Identify system boundaries, assumptions, and edge cases."),
            ("Conclusion & Recommendations", "Synthesize technical recommendations grounded in evidence."),
            ("References", "List verified source citations."),
        ],
        "comparative_analysis": [
            ("Executive Summary", "High-level summary of comparative analysis."),
            ("Comparison Overview & Criteria", "Define evaluation criteria across documents."),
            ("Methodology & Approach Comparison", "Compare techniques and architectures across documents."),
            ("Performance & Result Metrics", "Contrast quantitative or qualitative results."),
            ("Trade-offs & Key Differences", "Highlight advantages, disadvantages, and conflicting findings."),
            ("Conclusion & Synthesis", "Provide final evidence-grounded comparative synthesis."),
            ("References", "List verified source citations."),
        ],
        "research_report": [
            ("Executive Summary", "Comprehensive executive overview."),
            ("Introduction & Objectives", "Outline background and objectives."),
            ("Methodology & Search Scope", "Detail analyzed documents and retrieval scope."),
            ("Detailed Research Findings", "Synthesize key findings with source attribution."),
            ("Discussion & Critical Evaluation", "Evaluate evidence quality and research implications."),
            ("Limitations & Gaps", "Highlight uncertainties and unaddressed areas."),
            ("Conclusion", "Final research conclusions."),
            ("References", "List verified source citations."),
        ],
        "data_analysis_report": [
            ("Dataset Overview & Scope", "Report row/column counts, schema details, and parameters."),
            ("Exploratory Data Findings", "Summarize initial distributions and data structures."),
            ("Statistical Findings & Trends", "Analyze quantitative metrics, trends, and patterns."),
            ("Data Quality & Missing Values", "Highlight missing information or dataset constraints."),
            ("Analytical Synthesis & Conclusions", "Provide data-driven conclusions."),
            ("References", "List verified source citations."),
        ],
    }

    def __init__(
        self,
        llm_service: LLMService,
        retrieval_pipeline: RetrievalPipeline,
        retrieval_service: RetrievalService,
        reranking_service: RerankingService,
        qdrant_service: QdrantService,
        embedding_service: EmbeddingService,
        prompt_builder: PromptBuilder,
    ) -> None:
        self.llm = llm_service
        self.pipeline = retrieval_pipeline
        self.retrieval_service = retrieval_service
        self.reranking_service = reranking_service
        self.qdrant_service = qdrant_service
        self.embedding_service = embedding_service
        self.prompt_builder = prompt_builder
        self.parser = CitationParser()
        self.resolver = CitationResolver()

    async def generate_report(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        report_type: str = "research_summary",
        query: Optional[str] = None,
        conversation_id: Optional[uuid.UUID] = None,
        document_ids: Optional[List[uuid.UUID]] = None,
        is_streaming: bool = False,
        event_queue: Optional[asyncio.Queue] = None,
    ) -> Report:
        """Generate a complete structured research report."""
        settings = get_settings()

        # Validate project
        stmt = select(Project).where(Project.id == project_id)
        proj_res = await session.execute(stmt)
        project = proj_res.scalar_one_or_none()
        if not project:
            raise NotFoundException(f"Project with ID '{project_id}' not found.")

        # Determine title & research query
        research_query = query or f"Generate a comprehensive {report_type.replace('_', ' ')} for {project.name}"
        title = f"{project.name} - {report_type.replace('_', ' ').title()}"

        # Determine version number
        ver_stmt = select(func.max(Report.version)).where(
            Report.project_id == project_id, Report.report_type == report_type
        )
        ver_res = await session.execute(ver_stmt)
        max_ver = ver_res.scalar() or 0
        new_version = max_ver + 1

        # Create report record in DB (status: generating)
        report = Report(
            project_id=project_id,
            conversation_id=conversation_id,
            title=title,
            report_type=report_type,
            status="generating",
            version=new_version,
            content_json=None,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)

        if is_streaming and event_queue:
            await event_queue.put({
                "type": "report_started",
                "data": {"report_id": str(report.id), "title": title, "version": new_version}
            })

        try:
            # 1. Evidence collection via ResearchOrchestrator
            orchestrator = ResearchOrchestrator(
                llm_service=self.llm,
                retrieval_pipeline=self.pipeline,
                retrieval_service=self.retrieval_service,
                reranking_service=self.reranking_service,
                qdrant_service=self.qdrant_service,
                embedding_service=self.embedding_service,
                prompt_builder=self.prompt_builder,
            )

            context_chunks = []
            async for result in orchestrator.execute_research(
                session=session,
                project_id=project_id,
                query=research_query,
                document_ids=document_ids,
                is_streaming=False,
            ):
                if isinstance(result, list):
                    context_chunks = result

            registry = SourceRegistry()
            # Register context chunks in source registry
            for chunk in context_chunks:
                registry.register(chunk)

            # Build initial valid citation IDs map
            valid_source_ids = set(registry._registry.keys())

            # 2. Section-by-section generation
            template_sections = self.REPORT_TEMPLATES.get(
                report_type, self.REPORT_TEMPLATES["research_summary"]
            )
            total_sections = len(template_sections)
            generated_sections = []

            for sec_idx, (sec_title, sec_purpose) in enumerate(template_sections, 1):
                if is_streaming and event_queue:
                    await event_queue.put({
                        "type": "section_started",
                        "data": {"section_id": f"sec_{sec_idx}", "title": sec_title, "step": sec_idx, "total": total_sections}
                    })

                sec_content = await self._generate_section_content(
                    sec_title=sec_title,
                    sec_purpose=sec_purpose,
                    context_chunks=context_chunks,
                    registry=registry,
                )

                # Validate citations in section
                sec_content_validated = self._validate_and_sanitize_citations(sec_content, valid_source_ids)

                generated_sections.append({
                    "id": f"sec_{sec_idx}",
                    "title": sec_title,
                    "purpose": sec_purpose,
                    "content": sec_content_validated,
                })

                if is_streaming and event_queue:
                    await event_queue.put({
                        "type": "section_completed",
                        "data": {"section_id": f"sec_{sec_idx}", "title": sec_title}
                    })

            # 3. Assemble sources list metadata
            sources_list = []
            for sid, chunk in registry._registry.items():
                meta = chunk.get("metadata", {})
                loc_parts = []
                if meta.get("page_number"):
                    loc_parts.append(f"Page {meta['page_number']}")
                if meta.get("sheet_name"):
                    loc_parts.append(f"Sheet '{meta['sheet_name']}'")
                if meta.get("row_count") is not None:
                    loc_parts.append(f"{meta['row_count']} rows")
                loc_info = ", ".join(loc_parts) if loc_parts else "Document Context"

                sources_list.append({
                    "source_id": sid,
                    "document_id": str(chunk.get("document_id")),
                    "filename": meta.get("source_filename") or "Unknown Document",
                    "location_info": loc_info,
                })

            if is_streaming and event_queue:
                await event_queue.put({"type": "validation_started", "data": {"message": "Validating report evidence..."}})

            # Finalize report content JSON
            report_content = {
                "title": title,
                "report_type": report_type,
                "version": new_version,
                "sections": generated_sections,
                "sources": sources_list,
            }

            report.content_json = report_content
            report.status = "completed"
            await session.commit()
            await session.refresh(report)

            if is_streaming and event_queue:
                await event_queue.put({
                    "type": "report_completed",
                    "data": {"report_id": str(report.id), "title": title}
                })

            return report

        except Exception as exc:
            logger.error(f"Report generation failed: {exc}")
            report.status = "failed"
            await session.commit()
            raise RuntimeError(f"Report generation failed: {exc}") from exc

    async def regenerate_section(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        report_id: uuid.UUID,
        section_id: str,
    ) -> Report:
        """Regenerate a single section of a report while preserving user edits and other sections."""
        stmt = select(Report).where(Report.id == report_id, Report.project_id == project_id)
        res = await session.execute(stmt)
        report = res.scalar_one_or_none()
        if not report or not report.content_json:
            raise NotFoundException("Report or report content not found.")

        sections = report.content_json.get("sections", [])
        target_sec = None
        for sec in sections:
            if sec.get("id") == section_id:
                target_sec = sec
                break

        if not target_sec:
            raise NotFoundException(f"Section with ID '{section_id}' not found in report.")

        # Re-execute targeted retrieval for section objective
        sec_title = target_sec.get("title", "Section")
        sec_purpose = target_sec.get("purpose", "")
        query = f"{sec_title}: {sec_purpose}"

        candidates = await self.pipeline.retrieve_optimized(
            session=session,
            project_id=project_id,
            query=query,
            retrieval_service=self.retrieval_service,
            reranking_service=self.reranking_service,
            qdrant_service=self.qdrant_service,
            embedding_service=self.embedding_service,
            top_k=5,
        )

        registry = SourceRegistry()
        for c in candidates:
            registry.register(c)

        valid_sids = set(registry._registry.keys())

        new_content = await self._generate_section_content(
            sec_title=sec_title,
            sec_purpose=sec_purpose,
            context_chunks=candidates,
            registry=registry,
        )
        new_content_validated = self._validate_and_sanitize_citations(new_content, valid_sids)

        target_sec["content"] = new_content_validated
        target_sec["is_user_edited"] = False

        report.content_json["sections"] = sections
        session.add(report)
        await session.commit()
        await session.refresh(report)
        return report

    async def _generate_section_content(
        self,
        sec_title: str,
        sec_purpose: str,
        context_chunks: List[Dict[str, Any]],
        registry: SourceRegistry,
    ) -> str:
        """Generate content for a specific report section using context chunks."""
        context_text = "\n\n".join(
            f"[{registry.register(chunk)}] {chunk['text']}" for chunk in context_chunks
        )

        system_prompt = (
            "You are a senior research analyst generating a formal research report section.\n"
            "CRITICAL GROUNDING & CITATION RULES:\n"
            "1. Base your writing ONLY on the supplied evidence context.\n"
            "2. Cite factual claims using the exact source markers provided in the context (e.g. [S1], [S2]).\n"
            "3. If evidence is missing or incomplete, explicitly state the limitation. DO NOT invent facts.\n"
            "4. Write in professional, objective markdown paragraphs."
        )

        user_prompt = (
            f"SECTION TITLE: {sec_title}\n"
            f"SECTION OBJECTIVE: {sec_purpose}\n\n"
            f"SUPPLIED EVIDENCE CONTEXT:\n{context_text}\n\n"
            f"Write the content for the '{sec_title}' section:"
        )

        content = await self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
        return content.strip()

    def _validate_and_sanitize_citations(self, text: str, valid_source_ids: set) -> str:
        """Detect and remove any hallucinated citation tags like [S99] that do not exist in valid_source_ids."""
        cited_ids = self.parser.parse(text)
        sanitized_text = text

        for cid in cited_ids:
            if cid not in valid_source_ids:
                logger.warning(f"Detected invalid citation reference [{cid}]. Stripping tag.")
                sanitized_text = sanitized_text.replace(f"[{cid}]", "")

        return sanitized_text
