import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.agentic_research import (
    AgenticResearchEngine,
    GapDetector,
    ResearchPlanner,
    ToolRegistry,
)


def test_research_planner_create_plan() -> None:
    plan_comp = ResearchPlanner.create_plan("Compare BERT vs ResNet-50", mode="standard")
    assert len(plan_comp.tasks) == 2
    assert "BERT" in plan_comp.tasks[0].question or "first entity" in plan_comp.tasks[0].question

    plan_quick = ResearchPlanner.create_plan("What is accuracy?", mode="quick")
    assert len(plan_quick.tasks) == 1
    assert plan_quick.mode == "quick"


@pytest.mark.asyncio
async def test_tool_registry_search_limits() -> None:
    p_id = str(uuid.uuid4())
    with patch("app.services.agentic_research.default_retrieval_pipeline.retrieve_optimized", new_callable=AsyncMock) as mock_ret:
        mock_ret.return_value = []
        # Request top_k = 100 (exceeds MAX_TOP_K of 20)
        res = await ToolRegistry.search_documents(p_id, "query", top_k=100)
        assert res == []
        mock_ret.assert_called_once()
        _, kwargs = mock_ret.call_args
        assert kwargs["top_k"] == 20


def test_gap_detector_evaluation() -> None:
    # Single source evidence for comparison question should flag gap
    evidence_single = [
        {"chunk_id": "c1", "text": "BERT is transformer based", "metadata": {"source_filename": "bert.pdf"}}
    ]
    eval_res = GapDetector.evaluate(evidence_single, "Compare BERT vs GPT")
    assert len(eval_res["gaps"]) > 0


@pytest.mark.asyncio
async def test_agentic_research_execution() -> None:
    p_id = str(uuid.uuid4())

    with patch("app.services.agentic_research.default_retrieval_pipeline.retrieve_optimized", new_callable=AsyncMock) as mock_ret, \
         patch("app.services.agentic_research.default_llm_service.generate", new_callable=AsyncMock) as mock_gen:
        
        mock_ret.return_value = [
            type("Chunk", (), {"id": "c1", "text": "ResNet-50 achieved 93.4% accuracy.", "score": 0.95, "metadata": {"source_filename": "resnet.pdf"}})()
        ]
        mock_gen.return_value = "ResNet-50 achieved 93.4% accuracy [S1]."

        state = await AgenticResearchEngine.execute_research(p_id, "What is ResNet-50 accuracy?", mode="standard")

        assert state.status == "completed"
        assert state.iterations <= AgenticResearchEngine.MAX_RESEARCH_ITERATIONS
        assert state.tool_calls <= AgenticResearchEngine.MAX_TOTAL_TOOL_CALLS
        assert state.final_report is not None
        assert "93.4%" in state.final_report
