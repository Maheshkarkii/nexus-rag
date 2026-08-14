import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.db.models.document import Document
from app.services.research import ResearchPlanner, ResearchOrchestrator
from app.services.retrieval_pipeline import RetrievalPipeline
from app.services.retrieval import RetrievalService
from app.services.reranking import RerankingService
from app.services.qdrant import QdrantService
from app.services.embedding import EmbeddingService
from app.services.prompt_builder import PromptBuilder


@pytest.mark.asyncio
async def test_planner_simple_query_no_decomposition() -> None:
    # A simple query should return a simple complexity classification
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = '{"complexity": "simple", "steps": [{"id": "step_1", "question": "What is the dataset?"}]}'
    
    planner = ResearchPlanner(mock_llm)
    plan = await planner.generate_plan("What dataset was used?")
    assert plan["complexity"] == "simple"
    assert len(plan["steps"]) == 1


@pytest.mark.asyncio
async def test_planner_cycle_dependency_stripping() -> None:
    # A cyclic dependency plan should have its dependencies stripped for safety
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = (
        '{"complexity": "complex", "steps": ['
        '{"id": "step_1", "question": "Identify model.", "depends_on": ["step_2"]},'
        '{"id": "step_2", "question": "Identify accuracy.", "depends_on": ["step_1"]}'
        ']}'
    )
    
    planner = ResearchPlanner(mock_llm)
    plan = await planner.generate_plan("Which model achieved the highest accuracy, and what dataset was it evaluated on?")
    assert plan["complexity"] == "complex"
    assert plan["steps"][0]["depends_on"] == []
    assert plan["steps"][1]["depends_on"] == []


@pytest.mark.asyncio
@patch("app.services.retrieval.QdrantService")
async def test_orchestrator_resolves_and_executes(
    mock_qdrant_class: MagicMock,
    db_session: AsyncSession,
) -> None:
    # 1. Setup DB
    project = Project(id=uuid.uuid4(), name="Planning Workspace")
    db_session.add(project)
    await db_session.commit()

    doc = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="paper.pdf",
        stored_filename="paper_stored.pdf",
        storage_path="projects/paper.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size=100,
        status="ready",
    )
    db_session.add(doc)
    await db_session.commit()

    # 2. Mock Services
    mock_qdrant = MagicMock()
    mock_qdrant_class.return_value = mock_qdrant

    mock_llm = AsyncMock()
    # Mock planner query decomposition response
    mock_llm.generate.side_effect = [
        # Plan response
        '{"complexity": "complex", "steps": ['
        '{"id": "step_1", "question": "Find model used in Paper A.", "depends_on": []},'
        '{"id": "step_2", "question": "Find accuracy for that model.", "depends_on": ["step_1"]}'
        ']}',
        # Rewrite query for Step 2
        "Find accuracy for ResNet-50 in Paper A.",
        # Summary for Step 1
        "Paper A evaluated a ResNet-50 model.",
        # Summary for Step 2
        "Accuracy is reported as 93.4%."
    ]

    mock_retrieval_svc = AsyncMock()
    # Step 1 retrieval yields ResNet chunk; Step 2 yields Accuracy chunk
    mock_retrieval_svc.retrieve.side_effect = [
        [{"chunk_id": uuid.uuid4(), "document_id": doc.id, "project_id": project.id, "text": "Model evaluated is ResNet-50", "score": 0.9, "metadata": {}}],
        [{"chunk_id": uuid.uuid4(), "document_id": doc.id, "project_id": project.id, "text": "ResNet-50 accuracy is 93.4%", "score": 0.85, "metadata": {}}]
    ]

    mock_rerank_svc = MagicMock()
    mock_rerank_svc.rerank.side_effect = lambda query, candidates, top_k: candidates

    emb_svc = EmbeddingService(device="cpu")
    pipeline = RetrievalPipeline()
    prompt_builder = PromptBuilder()

    orchestrator = ResearchOrchestrator(
        llm_service=mock_llm,
        retrieval_pipeline=pipeline,
        retrieval_service=mock_retrieval_svc,
        reranking_service=mock_rerank_svc,
        qdrant_service=mock_qdrant,
        embedding_service=emb_svc,
        prompt_builder=prompt_builder,
    )

    # Execute research plan
    context_chunks = []
    async for result in orchestrator.execute_research(
        session=db_session,
        project_id=project.id,
        query="Which model achieved highest accuracy and what is the dataset?",
        is_streaming=False,
    ):
        if isinstance(result, list):
            context_chunks = result

    # Verify we gathered chunks for both steps in topological order
    assert len(context_chunks) == 2
    assert "ResNet-50" in context_chunks[0]["text"]
    assert "93.4%" in context_chunks[1]["text"]
