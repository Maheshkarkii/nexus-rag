import logging
import uuid
import time
import asyncio
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
settings = get_settings()
from app.core.exceptions import NotFoundException, BadRequestException
from app.db.models.message import Message
from app.services.embedding import EmbeddingService
from app.services.qdrant import QdrantService
from app.services.retrieval import RetrievalService
from app.services.reranking import RerankingService
from app.services.retrieval_pipeline import RetrievalPipeline
from app.services.prompt_builder import PromptBuilder
from app.services.llm import LLMService
from app.services.citation import SourceRegistry, CitationParser, CitationResolver
from app.services.conversation import (
    get_conversation_by_id,
    create_message,
    get_conversation_messages,
)
from app.services.query_rewriter import ConversationQueryRewriter
from app.services.research import ResearchOrchestrator
from app.services.data_analysis import DataAnalysisService
from app.services.answer_generation import GroundedAnswerGenerator, ClaimVerifier, EvidenceSufficiencyEvaluator
from app.core.observability import TraceSpan, GroundednessEvaluator, default_metrics_collector

logger = logging.getLogger("ai_research_assistant.services.rag")


async def get_conversation_document_scope(session: AsyncSession, conversation_id: uuid.UUID) -> Optional[List[uuid.UUID]]:
    """Scan conversation messages chronologically to find the most recent user-selected document scope."""
    db_messages = await get_conversation_messages(session, conversation_id, limit=100)
    for msg in reversed(db_messages):
        if msg.role == "user" and msg.metadata_json and "selected_document_ids" in msg.metadata_json:
            doc_ids_str = msg.metadata_json["selected_document_ids"]
            if doc_ids_str is not None:
                return [uuid.UUID(d) for d in doc_ids_str]
    return None


class RAGService:
    """Orchestrator for the RAG pipeline, retrieving context, constructing prompts, and calling LLMs."""

    def __init__(self) -> None:
        self.parser = CitationParser()
        self.resolver = CitationResolver()

    async def ask_question(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        query: str,
        retrieval_pipeline: RetrievalPipeline,
        retrieval_service: RetrievalService,
        reranking_service: RerankingService,
        qdrant_service: QdrantService,
        embedding_service: EmbeddingService,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
        top_k: int = 5,
        document_ids: Optional[List[uuid.UUID]] = None,
        file_types: Optional[List[str]] = None,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Orchestrate RAG flow: retrieve matching chunks, build prompt, run LLM inference, return grounded answer."""
        
        # 1. Validation and history loading
        history_dicts = []
        search_query = query
        effective_doc_ids = document_ids
        
        if conversation_id:
            conv = await get_conversation_by_id(session, conversation_id)
            if not conv:
                raise NotFoundException(message=f"Conversation with ID '{conversation_id}' was not found.")
            if conv.project_id != project_id:
                raise BadRequestException("Conversation does not belong to this project.")
            
            if document_ids is None:
                inherited = await get_conversation_document_scope(session, conversation_id)
                if inherited is not None:
                    effective_doc_ids = inherited
                    logger.info(f"Inherited document scope from conversation: {effective_doc_ids}")
            
            metadata = {}
            if effective_doc_ids is not None:
                metadata["selected_document_ids"] = [str(d) for d in effective_doc_ids]
            else:
                metadata["selected_document_ids"] = None
                
            await create_message(
                session=session,
                conversation_id=conversation_id,
                role="user",
                content=query,
                metadata_json=metadata,
            )
            
            db_messages = await get_conversation_messages(session, conversation_id, limit=settings.CONVERSATION_HISTORY_LIMIT)
            history_dicts = [{"role": m.role, "content": m.content} for m in db_messages[:-1]]
            
            if history_dicts:
                rewriter = ConversationQueryRewriter()
                search_query = await rewriter.rewrite(history_dicts, query, llm_service)

        # 2. Stage 22 Deterministic Data Analysis Path
        data_svc = DataAnalysisService(llm_service)
        analysis_res = await data_svc.analyze_query(
            session=session,
            project_id=project_id,
            query=search_query,
            document_ids=effective_doc_ids,
        )

        if analysis_res:
            logger.info("Executed deterministic structured data analysis.")
            answer_text = analysis_res["explanation"]
            
            if conversation_id:
                await create_message(
                    session=session,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer_text,
                    metadata_json={"analysis_provenance": analysis_res["analysis_result"].get("provenance")},
                )
            
            return {
                "query": query,
                "answer": answer_text,
                "citations": [],
                "conversation_id": conversation_id,
            }

        # 3. Stage 20 Research Orchestrator (Multi-step RAG path)
        logger.info(f"Running Stage 20 Research Orchestrator for query: '{search_query}' (original: '{query}') in project {project_id}")
        orchestrator = ResearchOrchestrator(
            llm_service=llm_service,
            retrieval_pipeline=retrieval_pipeline,
            retrieval_service=retrieval_service,
            reranking_service=reranking_service,
            qdrant_service=qdrant_service,
            embedding_service=embedding_service,
            prompt_builder=prompt_builder,
        )

        context_chunks = []
        async for result in orchestrator.execute_research(
            session=session,
            project_id=project_id,
            query=search_query,
            document_ids=effective_doc_ids,
            file_types=file_types,
            is_streaming=False,
        ):
            if isinstance(result, list):
                context_chunks = result

        if not context_chunks:
            logger.info("Retrieval returned empty context. Short-circuiting LLM call.")
            fallback_answer = "I couldn't find enough relevant information in the selected documents to answer this question."
            if conversation_id:
                await create_message(session=session, conversation_id=conversation_id, role="assistant", content=fallback_answer, metadata_json={"citations": []})
            return {
                "query": query,
                "answer": fallback_answer,
                "citations": [],
                "conversation_id": conversation_id,
            }

        registry = SourceRegistry()

        is_comparison = retrieval_pipeline.detect_comparison_intent(search_query)
        if is_comparison:
            system_prompt = prompt_builder.build_comparison_system_prompt()
        else:
            system_prompt = prompt_builder.build_system_prompt()

        user_prompt = prompt_builder.build_user_prompt(
            query=query,
            context_chunks=context_chunks,
            registry=registry,
            history=history_dicts,
        )

        try:
            answer_gen = GroundedAnswerGenerator(llm_service)
            gen_result = await answer_gen.generate_grounded_answer(
                query=query,
                context_chunks=context_chunks,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                registry=registry,
            )

            answer_clean = gen_result["answer"]
            citations = gen_result["citations"]
            
            if conversation_id:
                serializable_citations = []
                for cit in citations:
                    c_copy = dict(cit)
                    c_copy["document_id"] = str(c_copy["document_id"])
                    c_copy["chunk_id"] = str(c_copy["chunk_id"])
                    serializable_citations.append(c_copy)
                await create_message(
                    session=session,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer_clean,
                    metadata_json={
                        "citations": serializable_citations,
                        "grounding_metrics": gen_result["metrics"],
                        "sufficiency": gen_result["sufficiency"],
                    },
                )
            
            return {
                "query": query,
                "answer": answer_clean,
                "citations": citations,
                "conversation_id": conversation_id,
                "grounding_metrics": gen_result["metrics"],
                "sufficiency": gen_result["sufficiency"],
            }

        except Exception as exc:
            logger.error(f"RAG generation failed during LLM call: {exc}")
            raise RuntimeError(f"RAG generation failure: {exc}") from exc

    async def ask_question_stream(
        self,
        session: AsyncSession,
        project_id: uuid.UUID,
        query: str,
        retrieval_pipeline: RetrievalPipeline,
        retrieval_service: RetrievalService,
        reranking_service: RerankingService,
        qdrant_service: QdrantService,
        embedding_service: EmbeddingService,
        prompt_builder: PromptBuilder,
        llm_service: LLMService,
        top_k: int = 5,
        document_ids: Optional[List[uuid.UUID]] = None,
        file_types: Optional[List[str]] = None,
        conversation_id: Optional[uuid.UUID] = None,
    ):
        """Asynchronously orchestrate and stream retrieval, context, and LLM text generation steps."""
        start_time = time.time()
        
        yield {"type": "status", "data": {"stage": "initializing", "message": "Initializing workspace query..."}}

        history_dicts = []
        search_query = query
        effective_doc_ids = document_ids
        
        if conversation_id:
            conv = await get_conversation_by_id(session, conversation_id)
            if not conv:
                yield {"type": "error", "data": {"code": "CONVERSATION_NOT_FOUND", "message": f"Conversation with ID '{conversation_id}' was not found."}}
                return
            if conv.project_id != project_id:
                yield {"type": "error", "data": {"code": "PROJECT_ISOLATION_VIOLATION", "message": "Conversation does not belong to this project."}}
                return
            
            if document_ids is None:
                inherited = await get_conversation_document_scope(session, conversation_id)
                if inherited is not None:
                    effective_doc_ids = inherited
                    logger.info(f"Inherited document scope from conversation: {effective_doc_ids}")
            
            metadata = {}
            if effective_doc_ids is not None:
                metadata["selected_document_ids"] = [str(d) for d in effective_doc_ids]
            else:
                metadata["selected_document_ids"] = None
                
            await create_message(
                session=session,
                conversation_id=conversation_id,
                role="user",
                content=query,
                metadata_json=metadata,
            )
            
            db_messages = await get_conversation_messages(session, conversation_id, limit=settings.CONVERSATION_HISTORY_LIMIT)
            history_dicts = [{"role": m.role, "content": m.content} for m in db_messages[:-1]]
            
            if history_dicts:
                yield {"type": "status", "data": {"stage": "query_rewriting", "message": "Analyzing conversation context..."}}
                rewriter = ConversationQueryRewriter()
                search_query = await rewriter.rewrite(history_dicts, query, llm_service)

        # Stage 22 Deterministic Data Analysis Check
        data_svc = DataAnalysisService(llm_service)
        analysis_res = await data_svc.analyze_query(
            session=session,
            project_id=project_id,
            query=search_query,
            document_ids=effective_doc_ids,
        )

        if analysis_res:
            yield {"type": "status", "data": {"stage": "data_analysis", "message": "Executing deterministic calculations..."}}
            answer_text = analysis_res["explanation"]
            
            if conversation_id:
                await create_message(
                    session=session,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer_text,
                    metadata_json={"analysis_provenance": analysis_res["analysis_result"].get("provenance")},
                )
            
            yield {"type": "token", "data": {"content": answer_text}}
            yield {"type": "complete", "data": {"metadata": {"latency_ms": int((time.time() - start_time) * 1000)}}}
            return

        yield {"type": "status", "data": {"stage": "retrieving", "message": "Searching your documents..."}}
        
        try:
            orchestrator = ResearchOrchestrator(
                llm_service=llm_service,
                retrieval_pipeline=retrieval_pipeline,
                retrieval_service=retrieval_service,
                reranking_service=reranking_service,
                qdrant_service=qdrant_service,
                embedding_service=embedding_service,
                prompt_builder=prompt_builder,
            )

            event_queue = asyncio.Queue()
            context_chunks = []

            async def run_research_in_background():
                nonlocal context_chunks
                try:
                    async for result in orchestrator.execute_research(
                        session=session,
                        project_id=project_id,
                        query=search_query,
                        document_ids=effective_doc_ids,
                        file_types=file_types,
                        is_streaming=True,
                        event_queue=event_queue,
                    ):
                        if isinstance(result, list):
                            context_chunks = result
                except Exception as e:
                    logger.error(f"Background research task failed: {e}")
                finally:
                    await event_queue.put(None)

            research_task = asyncio.create_task(run_research_in_background())

            while True:
                event = await event_queue.get()
                if event is None:
                    break
                yield event

            await research_task

        except Exception as exc:
            logger.error(f"Streaming retrieval stage failed: {exc}")
            yield {"type": "error", "data": {"code": "RETRIEVAL_FAILED", "message": "Retrieval process failed."}}
            return

        if not context_chunks:
            yield {"type": "status", "data": {"stage": "generating", "message": "Completing answer..."}}
            fallback_answer = "I couldn't find enough relevant information in the selected documents to answer this question."
            if conversation_id:
                await create_message(session=session, conversation_id=conversation_id, role="assistant", content=fallback_answer, metadata_json={"citations": []})
            yield {"type": "token", "data": {"content": fallback_answer}}
            yield {"type": "complete", "data": {"metadata": {"latency_ms": int((time.time() - start_time) * 1000)}}}
            return

        yield {"type": "status", "data": {"stage": "preparing_context", "message": "Preparing grounding context..."}}
        
        registry = SourceRegistry()
        
        is_comparison = retrieval_pipeline.detect_comparison_intent(search_query)
        if is_comparison:
            system_prompt = prompt_builder.build_comparison_system_prompt()
        else:
            system_prompt = prompt_builder.build_system_prompt()

        user_prompt = prompt_builder.build_user_prompt(
            query=query,
            context_chunks=context_chunks,
            registry=registry,
            history=history_dicts,
        )

        sources_list = []
        for sid, chunk in registry._registry.items():
            meta = chunk.get("metadata", {})
            sources_list.append({
                "source_id": sid,
                "document_id": chunk.get("document_id"),
                "filename": meta.get("source_filename") or "Unknown Document",
                "page_number": meta.get("page_number"),
                "sheet_name": meta.get("sheet_name"),
            })

        yield {"type": "sources", "data": {"sources": sources_list}}
        yield {"type": "status", "data": {"stage": "generating", "message": "Generating answer..."}}

        accumulated_text = ""
        ttft = None
        
        try:
            async for token in llm_service.stream(system_prompt=system_prompt, user_prompt=user_prompt):
                if ttft is None:
                    ttft = time.time()
                    logger.info(f"Time to First Token: {int((ttft - start_time) * 1000)}ms")
                accumulated_text += token
                yield {"type": "token", "data": {"content": token}}
        except Exception as exc:
            logger.error(f"LLM streaming generated error: {exc}")
            yield {"type": "error", "data": {"code": "GENERATION_FAILED", "message": "LLM generation was interrupted."}}
            return

        answer_clean = accumulated_text.strip()
        cited_ids = self.parser.parse(answer_clean)
        citations = self.resolver.resolve(cited_ids, registry)

        if conversation_id:
            serializable_citations = []
            for cit in citations:
                c_copy = dict(cit)
                c_copy["document_id"] = str(c_copy["document_id"])
                c_copy["chunk_id"] = str(c_copy["chunk_id"])
                serializable_citations.append(c_copy)
            await create_message(
                session=session,
                conversation_id=conversation_id,
                role="assistant",
                content=answer_clean,
                metadata_json={"citations": serializable_citations},
            )

        yield {"type": "citations", "data": {"citations": citations}}
        total_latency = int((time.time() - start_time) * 1000)
        yield {
            "type": "complete",
            "data": {
                "metadata": {
                    "latency_ms": total_latency,
                    "ttft_ms": int((ttft - start_time) * 1000) if ttft else None,
                }
            }
        }


default_rag_service = RAGService()


def get_rag_service() -> RAGService:
    return default_rag_service
