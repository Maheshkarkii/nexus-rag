import logging
import uuid
import json
import asyncio
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import BadRequestException
from app.services.llm import LLMService
from app.services.retrieval_pipeline import RetrievalPipeline
from app.services.retrieval import RetrievalService
from app.services.reranking import RerankingService
from app.services.qdrant import QdrantService
from app.services.embedding import EmbeddingService
from app.services.prompt_builder import PromptBuilder
from app.services.citation import SourceRegistry, CitationParser, CitationResolver

logger = logging.getLogger("ai_research_assistant.services.research")


class ResearchPlanner:
    """Decomposes complex queries into structured execution plans."""

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    async def generate_plan(self, query: str, max_steps: int = 5) -> Dict[str, Any]:
        """Classify complexity and decompose the user query into research steps."""
        system_prompt = (
            "You are a structured research query planner.\n"
            "Analyze the user's research question and decide if it requires multiple distinct information retrieval steps (decomposition).\n"
            "If the question is simple, return a JSON object with complexity = 'simple' and a single step containing the original query.\n"
            "If it is complex (e.g. comparing multiple aspects, requiring intermediate findings, or addressing multiple sub-questions), decompose it into the minimum number of logical steps.\n\n"
            "CRITICAL RULES:\n"
            "1. Define dependencies clearly using the step IDs. If Step 2 query depends on knowing the result of Step 1, set depends_on = ['step_1'].\n"
            "2. Avoid cyclic dependencies. A step cannot depend on itself or lead to a cycle.\n"
            "3. Return ONLY a valid JSON object. Do not include markdown formatting tags, explanation, or comments.\n\n"
            "JSON Schema:\n"
            "{\n"
            "  \"complexity\": \"simple\" | \"complex\",\n"
            "  \"steps\": [\n"
            "    {\n"
            "      \"id\": \"step_1\",\n"
            "      \"question\": \"Sub-query text to retrieve from documents\",\n"
            "      \"purpose\": \"Brief explanation of this step's purpose\",\n"
            "      \"depends_on\": []\n"
            "    }\n"
            "  ]\n"
            "}\n"
        )

        user_prompt = f"User Question: {query}\nDecompose into at most {max_steps} steps."

        try:
            raw_response = await self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
            # Remove any markdown code block wrappers
            clean_json = re.sub(r"^```json\s*|```\s*$", "", raw_response.strip(), flags=re.MULTILINE)
            plan = json.loads(clean_json)

            # Basic structure validation
            if "complexity" not in plan or "steps" not in plan or not isinstance(plan["steps"], list):
                raise ValueError("Invalid schema returned by LLM planner.")

            # Validate cycle check and step limit
            steps = plan["steps"][:max_steps]
            plan["steps"] = self._validate_and_sanitize_dependencies(steps)
            return plan

        except Exception as exc:
            logger.warning(f"Research planning failed: {exc}. Falling back to simple query.")
            return {
                "complexity": "simple",
                "steps": [
                    {
                        "id": "step_1",
                        "question": query,
                        "purpose": "Direct retrieval fallback",
                        "depends_on": [],
                    }
                ],
            }

    def _validate_and_sanitize_dependencies(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate dependencies to prevent cycles and clean up invalid references."""
        step_ids = {s["id"] for s in steps}
        sanitized = []

        # Build adjacency graph
        adj: Dict[str, Set[str]] = {s["id"]: set() for s in steps}
        for s in steps:
            deps = s.get("depends_on", [])
            for d in deps:
                if d in step_ids and d != s["id"]:
                    adj[s["id"]].add(d)

        # Detect cycles using DFS
        visited: Dict[str, int] = {sid: 0 for sid in step_ids} # 0=unvisited, 1=visiting, 2=visited

        def has_cycle(u: str) -> bool:
            visited[u] = 1
            for v in adj[u]:
                if visited[v] == 1:
                    return True
                if visited[v] == 0:
                    if has_cycle(v):
                        return True
            visited[u] = 2
            return False

        has_any_cycle = False
        for sid in step_ids:
            if visited[sid] == 0:
                if has_cycle(sid):
                    has_any_cycle = True
                    break

        for s in steps:
            # If graph is cyclic, strip dependencies to execute safely
            s["depends_on"] = [] if has_any_cycle else [d for d in s.get("depends_on", []) if d in step_ids]
            sanitized.append(s)

        return sanitized


class ResearchOrchestrator:
    """Executes multi-step research plans, resolving dependencies, deduplicating evidence, and synthesizing final grounded answers."""

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
        self.planner = ResearchPlanner(llm_service)

    async def execute_research(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        query: str,
        document_ids: Optional[List[uuid.UUID]] = None,
        file_types: Optional[List[str]] = None,
        is_streaming: bool = False,
        event_queue: Optional[asyncio.Queue] = None,
    ):
        """Execute the planning, step execution, and final synthesis phases of Stage 20."""
        settings = get_settings()
        
        # 1. Generate plan
        plan = await self.planner.generate_plan(query, max_steps=settings.MAX_RESEARCH_STEPS)
        
        if plan["complexity"] == "simple":
            logger.info("Simple query detected. Falling back directly to retrieve_optimized context chunks.")
            if is_streaming and event_queue:
                await event_queue.put({"type": "status", "data": {"stage": "retrieving", "message": "Searching your documents..."}})
            
            chunks = await self.pipeline.retrieve_optimized(
                session=session,
                project_id=project_id,
                query=query,
                retrieval_service=self.retrieval_service,
                reranking_service=self.reranking_service,
                qdrant_service=self.qdrant_service,
                embedding_service=self.embedding_service,
                top_k=settings.FINAL_CONTEXT_K,
                document_ids=document_ids,
                file_types=file_types,
            )
            yield chunks
            return

        # Complex query planning workflow
        steps = plan["steps"]
        total_steps = len(steps)
        
        if is_streaming and event_queue:
            await event_queue.put({
                "type": "research_started",
                "data": {"plan": plan, "message": f"Decomposed query into {total_steps} research steps."}
            })

        # Evidence Registry mapping step_id to retrieved chunks list
        evidence_registry: Dict[str, List[Dict[str, Any]]] = {}
        step_results: Dict[str, str] = {} # Mapped summary results to resolve dependencies
        completed_steps: Set[str] = set()
        failed_steps: Set[str] = set()

        # Define event emitter callback to pass to tasks
        async def on_step_event(evt: Dict[str, Any]):
            if is_streaming and event_queue:
                await event_queue.put(evt)

        # Simple topological sort/level-by-level execution to resolve dependencies in order
        while len(completed_steps) + len(failed_steps) < total_steps:
            # Find steps that are ready
            ready_steps = []
            for s in steps:
                s_id = s["id"]
                if s_id in completed_steps or s_id in failed_steps:
                    continue
                deps = s.get("depends_on", [])
                if all((d in completed_steps or d in failed_steps) for d in deps):
                    ready_steps.append(s)

            if not ready_steps:
                break

            # Execute ready steps in parallel
            tasks = []
            for s in ready_steps:
                tasks.append(self._execute_step(
                    session=session,
                    project_id=project_id,
                    step=s,
                    step_results=step_results,
                    document_ids=document_ids,
                    file_types=file_types,
                    on_event=on_step_event,
                    total_steps=total_steps,
                    step_num=len(completed_steps) + len(failed_steps) + 1,
                ))

            res_list = await asyncio.gather(*tasks, return_exceptions=True)

            for s, res in zip(ready_steps, res_list):
                s_id = s["id"]
                if isinstance(res, Exception):
                    logger.error(f"Research step {s_id} failed: {res}")
                    failed_steps.add(s_id)
                    evidence_registry[s_id] = []
                    step_results[s_id] = "Failed to retrieve evidence."
                else:
                    chunks, summary = res
                    evidence_registry[s_id] = chunks
                    step_results[s_id] = summary
                    completed_steps.add(s_id)

        # 2. Evidence Deduplication & Context Budgeting
        deduplicated_chunks = []
        seen_chunk_ids = set()
        current_tokens = 0
        max_tokens = settings.RESEARCH_CONTEXT_BUDGET

        def est_tokens(text: str) -> int:
            return int(len(text.split()) * 1.3)

        for s_id in step_results.keys():
            chunks = evidence_registry.get(s_id, [])
            for c in chunks:
                uid = c.get("chunk_id") or c.get("id")
                if uid not in seen_chunk_ids:
                    tokens = est_tokens(c["text"])
                    if current_tokens + tokens <= max_tokens:
                        seen_chunk_ids.add(uid)
                        deduplicated_chunks.append(c)
                        current_tokens += tokens

        yield deduplicated_chunks

    async def _execute_step(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        step: Dict[str, Any],
        step_results: Dict[str, str],
        document_ids: Optional[List[uuid.UUID]] = None,
        file_types: Optional[List[str]] = None,
        on_event: Optional[Any] = None,
        total_steps: int = 1,
        step_num: int = 1,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Execute a single step retrieval, resolving dependencies if present."""
        s_id = step["id"]
        question = step["question"]
        deps = step.get("depends_on", [])

        if on_event:
            await on_event({
                "type": "research_step_started",
                "data": {"id": s_id, "question": question, "step": step_num, "total_steps": total_steps}
            })

        # Resolve dependencies by query rewriting
        if deps:
            dep_evidence = []
            for d in deps:
                dep_evidence.append(f"Answer/Evidence from prerequisite [{d}]: {step_results.get(d, 'No evidence')}")
            context_str = "\n".join(dep_evidence)
            
            rewrite_system = (
                "You are an expert search query formulation assistant.\n"
                "Your task is to rewrite the research sub-question using the prerequisite context provided.\n"
                "Resolve all placeholders and pronoun references to exact entities. Return ONLY the rewritten query."
            )
            rewrite_user = (
                f"Prerequisite Context:\n{context_str}\n\n"
                f"Sub-question: {question}\n\n"
                "Rewritten Sub-question:"
            )
            try:
                rewritten_q = await self.llm.generate(system_prompt=rewrite_system, user_prompt=rewrite_user)
                question = rewritten_q.strip()
                logger.info(f"Step {s_id} rewritten query: {question}")
            except Exception as e:
                logger.warning(f"Failed to rewrite step {s_id} query: {e}")

        # Execute retrieval and reranking for this step
        settings = get_settings()
        chunks = await self.pipeline.retrieve_optimized(
            session=session,
            project_id=project_id,
            query=question,
            retrieval_service=self.retrieval_service,
            reranking_service=self.reranking_service,
            qdrant_service=self.qdrant_service,
            embedding_service=self.embedding_service,
            top_k=settings.FINAL_CONTEXT_K,
            document_ids=document_ids,
            file_types=file_types,
        )

        # Generate a small summary of this step's evidence for dependency resolution
        summary = "No evidence found."
        if chunks:
            summary_system = (
                "Summarize the provided context in 1-2 sentences strictly answering the query. "
                "Do not invent information. Be concise."
            )
            summary_user = f"Query: {question}\n\nContext:\n" + "\n".join(c["text"] for c in chunks)
            try:
                summary_res = await self.llm.generate(system_prompt=summary_system, user_prompt=summary_user)
                summary = summary_res.strip()
            except Exception:
                summary = chunks[0]["text"][:200]

        if on_event:
            await on_event({
                "type": "research_step_completed",
                "data": {"id": s_id, "question": question, "status": "success" if chunks else "no_evidence"}
            })

        return chunks, summary
