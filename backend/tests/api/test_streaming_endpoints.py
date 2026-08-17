import uuid
from unittest.mock import MagicMock, patch
import httpx
import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project


@pytest.mark.asyncio
@patch("app.services.retrieval.QdrantService")
@patch("app.services.reranking.CrossEncoder")
@patch("app.services.llm.AsyncOpenAI")
async def test_ask_stream_endpoint_success(
    mock_openai_class: MagicMock,
    mock_cross_encoder_class: MagicMock,
    mock_qdrant_class: MagicMock,
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    # 1. Mock Qdrant
    mock_qdrant = MagicMock()
    mock_qdrant.health_check.return_value = True
    mock_qdrant_class.return_value = mock_qdrant

    mock_hit = MagicMock()
    mock_hit.score = 0.90
    mock_hit.payload = {
        "chunk_id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "chunk_index": 0,
        "text": "True evidence block content.",
        "source_filename": "docs.pdf",
    }
    mock_qclient = MagicMock()
    mock_qresponse = MagicMock()
    mock_qresponse.points = [mock_hit]
    mock_qclient.query_points.return_value = mock_qresponse
    mock_qclient.search.return_value = [mock_hit]
    mock_qdrant.connect.return_value = mock_qclient

    # 2. Mock Reranker
    from app.services.reranking import default_reranking_service
    default_reranking_service._model = None
    mock_rerank_instance = MagicMock()
    mock_cross_encoder_class.return_value = mock_rerank_instance
    mock_rerank_instance.predict.return_value = [3.0]

    # 3. Mock OpenAI Chat stream completions
    from app.services.llm import default_llm_service
    default_llm_service._client = None

    mock_openai = MagicMock()
    mock_openai_class.return_value = mock_openai

    class Delta:
        def __init__(self, content):
            self.content = content
    class Choice:
        def __init__(self, content):
            self.delta = Delta(content)
    class Chunk:
        def __init__(self, content):
            self.choices = [Choice(content)]

    class AsyncIteratorMock:
        def __init__(self, items):
            self.items = items
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not self.items:
                raise StopAsyncIteration
            return self.items.pop(0)

    from unittest.mock import AsyncMock
    mock_openai.chat.completions.create = AsyncMock(
        return_value=AsyncIteratorMock([
            Chunk("The "),
            Chunk("answer "),
            Chunk("is [S1].")
        ])
    )

    from app.services.qdrant import get_qdrant_service
    from app.main import app
    
    default_llm_service.api_key = "test-mock-key"
    app.dependency_overrides[get_qdrant_service] = lambda: mock_qdrant

    try:
        # Setup project in DB
        project = Project(id=uuid.uuid4(), name="Ask Stream Project")
        db_session.add(project)
        await db_session.commit()

        payload = {"query": "Find answer?", "top_k": 3}
        
        # Call Streaming Endpoint using client stream method
        async with async_client.stream(
            "POST",
            f"/api/v1/projects/{project.id}/ask/stream",
            json=payload,
        ) as response:
            assert response.status_code == status.HTTP_200_OK
            assert "text/event-stream" in response.headers["content-type"]
            
            # Read streaming content lines
            lines = []
            async for line in response.aiter_lines():
                if line:
                    lines.append(line)

            print("STREAM LINES:", lines)
            assert len(lines) > 0
            # Matches event lines: "event: token" followed by "data: {"content": "..."}"
            assert any("event: initializing" in l or "event: status" in l for l in lines)
            assert any("event: sources" in l for l in lines)
            assert any("event: token" in l for l in lines)
            assert any("event: citations" in l for l in lines)
            assert any("event: complete" in l for l in lines)

    finally:
        app.dependency_overrides.clear()
        default_llm_service.api_key = None
