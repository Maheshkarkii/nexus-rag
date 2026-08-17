import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.project import Project
from app.services.embedding import EmbeddingService
from app.services.retrieval_pipeline import RetrievalPipeline


def test_comparison_intent_detection() -> None:
    pipeline = RetrievalPipeline()
    assert pipeline.detect_comparison_intent("Compare the methodologies of Paper A and Paper B") is True
    assert pipeline.detect_comparison_intent("What is the difference between model X and model Y?") is True
    assert pipeline.detect_comparison_intent("Which approach performs better?") is True
    assert pipeline.detect_comparison_intent("What optimizer was used in the training process?") is False
    assert pipeline.detect_comparison_intent("Summarize this paper") is False


@pytest.mark.asyncio
@patch("app.services.retrieval.QdrantService")
async def test_retrieve_comparison_balances_evidence(
    mock_qdrant_class: MagicMock,
    db_session: AsyncSession,
) -> None:
    # 1. Setup DB project and documents
    project = Project(id=uuid.uuid4(), name="Comparison Workspace")
    db_session.add(project)
    await db_session.commit()

    doc_a = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="paper_a.pdf",
        stored_filename="paper_a_stored.pdf",
        storage_path="projects/paper_a.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size=100,
        status="ready",
    )
    doc_b = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="paper_b.pdf",
        stored_filename="paper_b_stored.pdf",
        storage_path="projects/paper_b.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        file_size=100,
        status="ready",
    )
    db_session.add_all([doc_a, doc_b])
    await db_session.commit()

    # 2. Mock Qdrant Service
    mock_qdrant = MagicMock()
    mock_qdrant.health_check.return_value = True
    mock_qdrant.collection_exists.return_value = True
    mock_qdrant.collection_name = "research_documents"
    mock_qdrant_class.return_value = mock_qdrant

    # Generate 5 candidates: 4 for Doc A and 1 for Doc B
    # Global retrieval should return these candidates, and our pipeline will balance them
    candidates = [
        {
            "chunk_id": uuid.uuid4(),
            "document_id": doc_a.id,
            "project_id": project.id,
            "text": f"Paper A methodology detail {i}",
            "score": 0.9 - i * 0.05,
            "chunk_index": i,
            "metadata": {"source_filename": "paper_a.pdf", "file_type": ".pdf"},
        }
        for i in range(4)
    ] + [
        {
            "chunk_id": uuid.uuid4(),
            "document_id": doc_b.id,
            "project_id": project.id,
            "text": "Paper B methodology detail 0",
            "score": 0.82,
            "chunk_index": 0,
            "metadata": {"source_filename": "paper_b.pdf", "file_type": ".pdf"},
        }
    ]

    mock_retrieval_svc = AsyncMock()
    mock_retrieval_svc.retrieve.return_value = candidates

    mock_rerank_svc = MagicMock()
    # Reranking simply returns candidates sorted/filtered
    mock_rerank_svc.rerank.side_effect = lambda query, candidates, top_k: candidates[:top_k]

    emb_svc = EmbeddingService(device="cpu")
    pipeline = RetrievalPipeline()

    # Call comparison retrieval
    results = await pipeline.retrieve_comparison(
        session=db_session,
        project_id=project.id,
        query="compare methodologies",
        retrieval_service=mock_retrieval_svc,
        reranking_service=mock_rerank_svc,
        qdrant_service=mock_qdrant,
        embedding_service=emb_svc,
        document_ids=[doc_a.id, doc_b.id],
    )

    # Verify evidence balancing
    # The pipeline should take doc_a's first chunk, then doc_b's first chunk, and so on.
    # Therefore, both doc_a and doc_b must be represented, preventing doc_a from completely dominating the context.
    doc_ids_in_results = [r["document_id"] for r in results]
    assert doc_a.id in doc_ids_in_results
    assert doc_b.id in doc_ids_in_results


@pytest.mark.asyncio
async def test_csv_metadata_statistics_injection(db_session: AsyncSession) -> None:
    # Test that structured dataset files automatically inject exact metadata summaries
    project = Project(id=uuid.uuid4(), name="Dataset Workspace")
    db_session.add(project)
    await db_session.commit()

    csv_doc = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="experiment_data.csv",
        stored_filename="experiment_data_stored.csv",
        storage_path="projects/experiment_data.csv",
        mime_type="text/csv",
        file_extension=".csv",
        file_size=1000,
        status="ready",
        extracted_metadata={
            "column_names": ["id", "val", "label"],
            "column_count": 3,
            "row_count": 150,
        }
    )
    db_session.add(csv_doc)
    await db_session.commit()

    mock_retrieval_svc = AsyncMock()
    mock_retrieval_svc.retrieve.return_value = []

    mock_rerank_svc = MagicMock()
    mock_qdrant = MagicMock()
    emb_svc = EmbeddingService(device="cpu")
    pipeline = RetrievalPipeline()

    results = await pipeline.retrieve_comparison(
        session=db_session,
        project_id=project.id,
        query="compare row counts",
        retrieval_service=mock_retrieval_svc,
        reranking_service=mock_rerank_svc,
        qdrant_service=mock_qdrant,
        embedding_service=emb_svc,
        document_ids=[csv_doc.id],
    )

    assert len(results) == 1
    assert results[0]["document_id"] == csv_doc.id
    assert "File Statistics & Structure:" in results[0]["text"]
    assert "150 rows" in results[0]["text"]
    assert "id, val, label" in results[0]["text"]
