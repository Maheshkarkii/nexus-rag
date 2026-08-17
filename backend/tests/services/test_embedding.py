import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.embedding import ChunkEmbedding
from app.db.models.project import Project
from app.services.document_processing.chunking.service import ChunkingService
from app.services.embedding import EmbeddingService


# ------------------------------------------------------------------------------
# 1. Embedding Service Unit Tests
# ------------------------------------------------------------------------------
def test_embedding_service_model_metadata() -> None:
    # Uses default config-defined model
    service = EmbeddingService(device="cpu")
    dim = service.get_dimension()
    assert dim == 384
    assert service.model_name == "sentence-transformers/all-MiniLM-L6-v2"


def test_embedding_device_resolutions() -> None:
    service_cpu = EmbeddingService(device="cpu")
    assert service_cpu._resolve_device() == "cpu"

    service_auto = EmbeddingService(device="auto")
    assert service_auto._resolve_device() in ("cpu", "cuda")

    # If CUDA requested but unavailable, should raise ValueError
    import torch
    if not torch.cuda.is_available():
        service_cuda = EmbeddingService(device="cuda")
        with pytest.raises(ValueError, match="CUDA GPU acceleration was explicitly requested"):
            service_cuda._resolve_device()


def test_embed_single_text() -> None:
    service = EmbeddingService(device="cpu")
    vector = service.embed_text("This is a simple query block.")
    assert len(vector) == 384
    assert all(isinstance(val, float) for val in vector)


def test_embed_batch_texts() -> None:
    service = EmbeddingService(device="cpu")
    texts = ["Sentence A", "Sentence B", "Sentence C"]
    vectors = service.embed_batch(texts)
    assert len(vectors) == 3
    for vec in vectors:
        assert len(vec) == 384


def test_embed_empty_handling() -> None:
    service = EmbeddingService(device="cpu")
    # Should skip empty lines safely and return empty lists or filter them
    assert service.embed_text("   ") == []
    assert service.embed_batch(["", "  "]) == []


# ------------------------------------------------------------------------------
# 2. Integration & Re-Embedding Lifecycle Tests
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_embedding_service_lifecycle_and_re_embedding(db_session: AsyncSession) -> None:
    # 1. Setup project, document, and chunks in DB
    project = Project(id=uuid.uuid4(), name="Embedding Workspace", description="Desc")
    db_session.add(project)
    await db_session.commit()

    document = Document(
        id=uuid.uuid4(),
        project_id=project.id,
        original_filename="manual_doc.txt",
        stored_filename="manual_doc_stored.txt",
        storage_path="projects/test/manual_doc.txt",
        mime_type="text/plain",
        file_extension=".txt",
        file_size=1024,
        status="ready",
        extracted_text="Methodology overview. Setup configurations. Result tables.",
        extracted_character_count=57,
    )
    db_session.add(document)
    await db_session.commit()

    # Create chunks first
    chunking_svc = ChunkingService()
    await chunking_svc.chunk_document(
        session=db_session,
        project_id=project.id,
        document_id=document.id,
        chunk_size=25,
        chunk_overlap=5,
    )

    # 2. Trigger embedding service
    embed_svc = EmbeddingService(device="cpu")
    res = await embed_svc.embed_document(
        session=db_session,
        project_id=project.id,
        document_id=document.id,
    )

    assert res["document_id"] == document.id
    assert res["chunk_count"] > 0
    assert res["embedded_count"] == res["chunk_count"]
    assert res["failed_count"] == 0
    assert res["dimension"] == 384
    assert res["device"] == "cpu"

    # Query DB to check if ChunkEmbedding records were created
    emb_stmt = select(ChunkEmbedding).join(DocumentChunk, DocumentChunk.id == ChunkEmbedding.chunk_id).where(DocumentChunk.document_id == document.id)
    emb_res = await db_session.execute(emb_stmt)
    embeddings = emb_res.scalars().all()
    assert len(embeddings) == res["embedded_count"]

    for emb in embeddings:
        assert emb.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert emb.dimension == 384
        assert len(emb.vector) == 384
        assert emb.status == "completed"
        assert emb.normalized is True

    # 3. Call embed_document again (Re-embedding)
    res2 = await embed_svc.embed_document(
        session=db_session,
        project_id=project.id,
        document_id=document.id,
    )
    assert res2["embedded_count"] == res["chunk_count"]

    # Verify we still have the exact same number of embeddings (old ones deleted and replaced)
    emb_res2 = await db_session.execute(emb_stmt)
    embeddings2 = emb_res2.scalars().all()
    assert len(embeddings2) == len(embeddings)
