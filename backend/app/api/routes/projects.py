"""REST API route handlers for Research Project workspace management."""

import uuid

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.schemas.rag import AskRequest, RAGResponse
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse
from app.services.embedding import EmbeddingService, get_embedding_service
from app.services.llm import LLMService, get_llm_service
from app.services.project import (
    create_project,
    delete_project,
    get_project_by_id,
    get_projects,
    update_project,
)
from app.services.prompt_builder import PromptBuilder, get_prompt_builder
from app.services.qdrant import QdrantService, get_qdrant_service
from app.services.rag import RAGService, get_rag_service
from app.services.reranking import RerankingService, get_reranking_service
from app.services.retrieval import RetrievalService, get_retrieval_service
from app.services.retrieval_pipeline import RetrievalPipeline, get_retrieval_pipeline

router = APIRouter()


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Research Project",
    description="Initialize and persist a new isolated research workspace.",
)
async def create_new_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new research project record."""
    project = await create_project(session=session, payload=payload)
    return ProjectResponse.model_validate(project)


@router.get(
    "",
    response_model=list[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="List Research Projects",
    description="Retrieve all research projects ordered by creation date descending.",
)
async def list_all_projects(
    session: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    """List all available research project workspaces."""
    projects = await get_projects(session=session)
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Research Project",
    description="Retrieve a single research project workspace by its UUID.",
)
async def get_single_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Fetch project details by primary key."""
    project = await get_project_by_id(session=session, project_id=project_id)
    if not project:
        raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")
    return ProjectResponse.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Research Project",
    description="Apply partial updates to a research project's name or description.",
)
async def update_existing_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update project title and/or description."""
    project = await get_project_by_id(session=session, project_id=project_id)
    if not project:
        raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")
    updated = await update_project(session=session, project=project, payload=payload)
    return ProjectResponse.model_validate(updated)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Research Project",
    description="Permanently delete a research project workspace.",
)
async def delete_existing_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Delete project by UUID primary key."""
    project = await get_project_by_id(session=session, project_id=project_id)
    if not project:
        raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")
    await delete_project(session=session, project=project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{project_id}/retrieve",
    response_model=RetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic Evidence Retrieval",
    description="Retrieve relevant document text chunks matching the semantic query in the project context.",
)
async def retrieve_evidence(
    project_id: uuid.UUID,
    payload: RetrievalRequest,
    session: AsyncSession = Depends(get_db),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    reranking_service: RerankingService = Depends(get_reranking_service),
    retrieval_pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    qdrant_service: QdrantService = Depends(get_qdrant_service),
) -> RetrievalResponse:
    """Retrieve relevant chunks from the vector database using query embeddings, filters, and reranking."""
    # 1. Verify project exists
    project = await get_project_by_id(session=session, project_id=project_id)
    if not project:
        raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")

    results = await retrieval_pipeline.retrieve_optimized(
        session=session,
        project_id=project_id,
        query=payload.query,
        retrieval_service=retrieval_service,
        reranking_service=reranking_service,
        qdrant_service=qdrant_service,
        embedding_service=embedding_service,
        top_k=payload.top_k,
        document_ids=payload.document_ids,
        file_types=payload.file_types,
    )
    return RetrievalResponse(query=payload.query, results=results)


@router.post(
    "/{project_id}/ask",
    response_model=RAGResponse,
    status_code=status.HTTP_200_OK,
    summary="Grounded Question Answering",
    description="Answer research questions using only document evidence retrieved from the project workspace.",
)
async def ask_research_question(
    project_id: uuid.UUID,
    payload: AskRequest,
    session: AsyncSession = Depends(get_db),
    retrieval_pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    reranking_service: RerankingService = Depends(get_reranking_service),
    qdrant_service: QdrantService = Depends(get_qdrant_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    prompt_builder: PromptBuilder = Depends(get_prompt_builder),
    llm_service: LLMService = Depends(get_llm_service),
    rag_service: RAGService = Depends(get_rag_service),
) -> RAGResponse:
    """Ask a question, retrieve evidence, and generate a grounded, source-attributed answer using an LLM."""
    # 1. Verify project exists
    project = await get_project_by_id(session=session, project_id=project_id)
    if not project:
        raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")

    response_data = await rag_service.ask_question(
        session=session,
        project_id=project_id,
        query=payload.query,
        retrieval_pipeline=retrieval_pipeline,
        retrieval_service=retrieval_service,
        reranking_service=reranking_service,
        qdrant_service=qdrant_service,
        embedding_service=embedding_service,
        prompt_builder=prompt_builder,
        llm_service=llm_service,
        top_k=payload.top_k,
        document_ids=payload.document_ids,
        file_types=payload.file_types,
        conversation_id=payload.conversation_id,
    )
    return RAGResponse.model_validate(response_data)


@router.post(
    "/{project_id}/ask/stream",
    summary="Progressive RAG Answer Streaming",
    description="Stream answers progressively to the frontend via Server-Sent Events (SSE).",
)
async def ask_research_question_stream(
    project_id: uuid.UUID,
    payload: AskRequest,
    session: AsyncSession = Depends(get_db),
    retrieval_pipeline: RetrievalPipeline = Depends(get_retrieval_pipeline),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    reranking_service: RerankingService = Depends(get_reranking_service),
    qdrant_service: QdrantService = Depends(get_qdrant_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    prompt_builder: PromptBuilder = Depends(get_prompt_builder),
    llm_service: LLMService = Depends(get_llm_service),
    rag_service: RAGService = Depends(get_rag_service),
) -> StreamingResponse:
    """Ask a question and stream response events (status, sources, tokens, citations, completion)."""
    import json
    
    class UUIDEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, uuid.UUID):
                return str(obj)
            return super().default(obj)
    
    # 1. Verify project exists
    project = await get_project_by_id(session=session, project_id=project_id)
    if not project:
        raise NotFoundException(message=f"Project with ID '{project_id}' was not found.")

    async def sse_event_generator():
        try:
            async for event in rag_service.ask_question_stream(
                session=session,
                project_id=project_id,
                query=payload.query,
                retrieval_pipeline=retrieval_pipeline,
                retrieval_service=retrieval_service,
                reranking_service=reranking_service,
                qdrant_service=qdrant_service,
                embedding_service=embedding_service,
                prompt_builder=prompt_builder,
                llm_service=llm_service,
                top_k=payload.top_k,
                document_ids=payload.document_ids,
                file_types=payload.file_types,
                conversation_id=payload.conversation_id,
            ):
                # Standard Server-Sent Events output format
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'], cls=UUIDEncoder)}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'code': 'STREAM_ERROR', 'message': str(exc)}, cls=UUIDEncoder)}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")



