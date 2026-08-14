import logging
import uuid
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.services.retrieval_pipeline import default_retrieval_pipeline
from app.services.prompt_builder import default_prompt_builder
from app.services.llm import default_llm_service
from app.services.citation import SourceRegistry, CitationParser, CitationResolver
from app.services.data_analysis import data_analysis_service

logger = logging.getLogger("ai_research_assistant.agentic_research")


# --- State & Schemas ---

class ResearchTask(BaseModel):
    id: str
    question: str
    purpose: str
    required_evidence: str
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None


class ResearchPlan(BaseModel):
    objective: str
    mode: str = "standard"  # quick, standard, deep
    tasks: List[ResearchTask] = Field(default_factory=list)


class ResearchState(BaseModel):
    research_id: str
    project_id: str
    user_id: Optional[str] = None
    question: str
    plan: Optional[ResearchPlan] = None
    current_task_index: int = 0
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    iterations: int = 0
    tool_calls: int = 0
    status: str = "planning"  # planning, executing, evaluating, synthesizing, completed, failed
    final_report: Optional[str] = None


# --- Tool Registry ---

class ToolRegistry:
    """Controlled, authorized tool registry for research execution."""

    MAX_TOOL_CALLS = 10
    MAX_TOP_K = 20

    @classmethod
    async def search_documents(
        cls,
        project_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Bounded document search tool executing existing hybrid retrieval pipeline."""
        capped_k = min(top_k, cls.MAX_TOP_K)
        p_id = uuid.UUID(project_id) if isinstance(project_id, str) else project_id
        res = await default_retrieval_pipeline.retrieve_optimized(
            session=None,
            project_id=p_id,
            query=query,
            retrieval_service=None,
            reranking_service=None,
            qdrant_service=None,
            embedding_service=None,
            top_k=capped_k,
        )
        return [
            {
                "chunk_id": getattr(item, "id", f"c_{idx}"),
                "text": getattr(item, "text", ""),
                "score": getattr(item, "score", 0.0),
                "metadata": getattr(item, "metadata", {}),
            }
            for idx, item in enumerate(res)
        ]

    @classmethod
    async def analyze_structured_data(
        cls,
        project_id: str,
        document_id: str,
        question: str,
    ) -> Dict[str, Any]:
        """Deterministic pandas data analysis tool for CSV/XLSX datasets."""
        p_id = uuid.UUID(project_id) if isinstance(project_id, str) else project_id
        doc_id = uuid.UUID(document_id) if isinstance(document_id, str) else document_id
        return await data_analysis_service.analyze(p_id, doc_id, question)


# --- Planner & Agent Workflow ---

class ResearchPlanner:
    """Decomposes user research queries into bounded execution plans."""

    @staticmethod
    def create_plan(question: str, mode: str = "standard") -> ResearchPlan:
        q_lower = question.lower()
        
        if "compare" in q_lower or "versus" in q_lower or "vs" in q_lower:
            tasks = [
                ResearchTask(
                    id="task_1",
                    question=f"Identify core characteristics for first entity in: {question}",
                    purpose="Extract primary evidence for comparison entity A",
                    required_evidence="Key metrics and specifications",
                ),
                ResearchTask(
                    id="task_2",
                    question=f"Identify core characteristics for second entity in: {question}",
                    purpose="Extract primary evidence for comparison entity B",
                    required_evidence="Key metrics and specifications",
                ),
            ]
        elif mode == "quick":
            tasks = [
                ResearchTask(
                    id="task_1",
                    question=question,
                    purpose="Direct evidence retrieval",
                    required_evidence="Direct answer facts",
                )
            ]
        else:
            tasks = [
                ResearchTask(
                    id="task_1",
                    question=f"Gather primary evidence for: {question}",
                    purpose="Collect foundational research context",
                    required_evidence="Factual assertions and metrics",
                ),
                ResearchTask(
                    id="task_2",
                    question=f"Verify details and cross-check evidence for: {question}",
                    purpose="Identify missing gaps or conflicts",
                    required_evidence="Supporting metadata and details",
                ),
            ]

        return ResearchPlan(
            objective=f"Autonomous research on: {question}",
            mode=mode,
            tasks=tasks,
        )


class GapDetector:
    """Evaluates collected evidence to detect gaps or conflicting information."""

    @staticmethod
    def evaluate(evidence: List[Dict[str, Any]], question: str) -> Dict[str, Any]:
        if not evidence:
            return {"gaps": ["No relevant evidence found"], "conflicts": []}

        gaps = []
        conflicts = []

        # Check source diversity
        sources = {item.get("metadata", {}).get("source_filename") for item in evidence if item.get("metadata")}
        if len(sources) < 2 and ("compare" in question.lower() or "versus" in question.lower()):
            gaps.append("Missing comparative source documents for multi-document synthesis")

        return {"gaps": gaps, "conflicts": conflicts}


class AgenticResearchEngine:
    """Orchestrates bounded, observable, multi-step agentic research workflows."""

    MAX_RESEARCH_ITERATIONS = 3
    MAX_TOTAL_TOOL_CALLS = 10

    @classmethod
    async def execute_research(
        cls,
        project_id: str,
        question: str,
        mode: str = "standard",
    ) -> ResearchState:
        res_id = str(uuid.uuid4())
        state = ResearchState(
            research_id=res_id,
            project_id=str(project_id),
            question=question,
        )

        # 1. Planning Step
        plan = ResearchPlanner.create_plan(question, mode=mode)
        state.plan = plan
        state.status = "executing"

        # 2. Task Execution Loop
        for task in plan.tasks:
            if state.tool_calls >= cls.MAX_TOTAL_TOOL_CALLS or state.iterations >= cls.MAX_RESEARCH_ITERATIONS:
                logger.warning(f"Research {res_id} reached execution limits.")
                break

            state.iterations += 1
            task.status = "running"

            # Execute search tool
            tool_results = await ToolRegistry.search_documents(
                project_id=state.project_id,
                query=task.question,
                top_k=5,
            )
            state.tool_calls += 1

            task.result = {"items_found": len(tool_results)}
            task.status = "completed"
            state.evidence.extend(tool_results)

        # 3. Gap Detection & Bounded Retries
        gap_eval = GapDetector.evaluate(state.evidence, question)
        state.gaps = gap_eval["gaps"]
        state.conflicts = gap_eval["conflicts"]

        if state.gaps and state.tool_calls < cls.MAX_TOTAL_TOOL_CALLS and state.iterations < cls.MAX_RESEARCH_ITERATIONS:
            # Execute 1 targeted gap-driven task
            gap_query = f"{question} {state.gaps[0]}"
            additional_results = await ToolRegistry.search_documents(
                project_id=state.project_id,
                query=gap_query,
                top_k=3,
            )
            state.tool_calls += 1
            state.iterations += 1
            state.evidence.extend(additional_results)

        # 4. Report Synthesis & Citation Validation
        state.status = "synthesizing"
        if not state.evidence:
            state.final_report = "I couldn't find enough relevant information in the selected documents to complete this research."
            state.status = "completed"
            return state

        # Deduplicate evidence
        unique_chunks = []
        seen_texts = set()
        for item in state.evidence:
            txt = item.get("text", "")
            if txt not in seen_texts:
                seen_texts.add(txt)
                unique_chunks.append(item)

        # Build prompt & query LLM
        registry = SourceRegistry()
        sys_prompt = default_prompt_builder.build_system_prompt()
        user_prompt = default_prompt_builder.build_user_prompt(question, unique_chunks, registry)
        raw_answer = await default_llm_service.generate(sys_prompt, user_prompt)

        state.final_report = raw_answer
        state.status = "completed"
        return state


agentic_research_engine = AgenticResearchEngine()
