"""REST API route handlers for research document upload, listing, processing, content, and deletion."""

import uuid

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.db.models.document_chunk import DocumentChunk
from app.db.models.embedding import ChunkEmbedding
from app.db.session import get_db
from app.schemas.document import DocumentContentResponse, DocumentResponse
from app.schemas.document_chunk import ChunkingSummaryResponse, DocumentChunkResponse
from app.schemas.embedding import EmbeddingMetadataResponse, EmbeddingSummaryResponse
from app.schemas.indexing import IndexingSummaryResponse
from app.services.document import (
    create_document,
    delete_document,
    get_document_by_id,
    get_documents_by_project,
)
from app.services.document_processing.chunking.service import (
    ChunkingService,
    get_chunking_service,
)
from app.services.document_processing.service import (
    DocumentProcessingService,
    get_processing_service,
)
from app.services.embedding import (
    EmbeddingService,
    get_embedding_service,
)
from app.services.indexing import (
    VectorIndexingService,
    get_indexing_service,
)
from app.services.qdrant import (
    QdrantService,
    get_qdrant_service,
)
from app.services.storage import StorageService, get_storage_service

router = APIRouter()


@router.post(
    "/{project_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Document to Project",
    description="Upload a research document (PDF, DOCX, TXT, CSV, XLSX, JSON) to an isolated workspace.",
)
async def upload_document_to_project(
    project_id: uuid.UUID,
    file: UploadFile = File(..., description="Binary research file to ingest"),
    session: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
) -> DocumentResponse:
    """Upload and record file metadata in the specified project workspace."""
    doc = await create_document(
        session=session,
        project_id=project_id,
        upload_file=file,
        storage_service=storage_service,
    )
    return DocumentResponse.model_validate(doc)


@router.get(
    "/{project_id}/documents",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List Project Documents",
    description="Retrieve all document metadata records belonging to the research project, ordered newest first.",
)
async def list_project_documents(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    """List document metadata for a project workspace."""
    docs = await get_documents_by_project(session=session, project_id=project_id)
    return [DocumentResponse.model_validate(d) for d in docs]


@router.get(
    "/{project_id}/documents/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Metadata",
    description="Retrieve metadata for a single document verifying project workspace ownership.",
)
async def get_single_document_metadata(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Fetch single document metadata by ID."""
    doc = await get_document_by_id(
        session=session, project_id=project_id, document_id=document_id
    )
    if not doc:
        raise NotFoundException(
            message=f"Document with ID '{document_id}' was not found in project '{project_id}'."
        )
    return DocumentResponse.model_validate(doc)


@router.post(
    "/{project_id}/documents/{document_id}/process",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Document and Extract Text",
    description="Trigger the format-specific parsing pipeline, extract structured content, and persist normalized text.",
)
async def process_project_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    processing_service: DocumentProcessingService = Depends(get_processing_service),
) -> DocumentResponse:
    """Execute text extraction and normalization for an uploaded research file."""
    doc = await processing_service.process_document(
        session=session,
        project_id=project_id,
        document_id=document_id,
        storage_service=storage_service,
    )
    return DocumentResponse.model_validate(doc)


@router.post(
    "/{project_id}/documents/{document_id}/pipeline",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Full Ingestion Pipeline (Extract, Chunk, Embed, Index)",
    description="Execute all processing stages sequentially in a single server-side call for optimal performance.",
)
async def run_full_ingestion_pipeline(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    chunk_size: int | None = Query(None, ge=50, le=4000, description="Optional custom chunk size in characters"),
    chunk_overlap: int | None = Query(None, ge=0, le=1000, description="Optional custom chunk overlap in characters"),
    session: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    processing_service: DocumentProcessingService = Depends(get_processing_service),
    chunking_service: ChunkingService = Depends(get_chunking_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    indexing_service: VectorIndexingService = Depends(get_indexing_service),
    qdrant_service: QdrantService = Depends(get_qdrant_service),
) -> DocumentResponse:
    """Run extract -> chunk -> embed -> index in a single fast server-side transaction."""
    # 1. Process / Extract text
    doc = await processing_service.process_document(
        session=session, project_id=project_id, document_id=document_id, storage_service=storage_service
    )
    if doc.status == "failed":
        raise BadRequestException(doc.processing_error or "Text extraction failed for document.")

    # 2. Chunk with user-configured chunk_size & chunk_overlap
    await chunking_service.chunk_document(
        session=session,
        project_id=project_id,
        document_id=document_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    # 3. Embed
    await embedding_service.embed_document(session=session, project_id=project_id, document_id=document_id)
    # 4. Index
    await indexing_service.index_document(
        session=session, project_id=project_id, document_id=document_id, qdrant_service=qdrant_service, embedding_service=embedding_service
    )
    await session.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.get(
    "/{project_id}/documents/{document_id}/content",
    response_model=DocumentContentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Extracted Document Content",
    description="Retrieve the extracted normalized text, statistics, and structured metadata of a document.",
)
async def get_document_extracted_content(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> DocumentContentResponse:
    """Fetch normalized extracted text and parsing metadata for verification and downstream chunking."""
    doc = await get_document_by_id(
        session=session, project_id=project_id, document_id=document_id
    )
    if not doc:
        raise NotFoundException(
            message=f"Document with ID '{document_id}' was not found in project '{project_id}'."
        )
    return DocumentContentResponse.model_validate(doc)


@router.delete(
    "/{project_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Document",
    description="Permanently delete a document physical file and its relational metadata record.",
)
async def delete_project_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
) -> Response:
    """Delete a document by UUID."""
    await delete_document(
        session=session,
        project_id=project_id,
        document_id=document_id,
        storage_service=storage_service,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{project_id}/documents/{document_id}/chunk",
    response_model=ChunkingSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Chunk Document",
    description="Partition extracted document text into structured chunks.",
)
async def chunk_project_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    chunk_size: int | None = Query(None, ge=50, le=4000, description="Optional custom chunk size in characters"),
    chunk_overlap: int | None = Query(None, ge=0, le=1000, description="Optional custom chunk overlap in characters"),
    session: AsyncSession = Depends(get_db),
    chunking_service: ChunkingService = Depends(get_chunking_service),
) -> ChunkingSummaryResponse:
    """Trigger format-specific chunking on extracted document text."""
    # 1. Fetch document and verify existence
    doc = await get_document_by_id(
        session=session, project_id=project_id, document_id=document_id
    )
    if not doc:
        raise NotFoundException(
            message=f"Document with ID '{document_id}' was not found in project '{project_id}'."
        )

    # 2. Verify extracted text exists
    if not doc.extracted_text or not doc.extracted_text.strip():
        raise BadRequestException(
            message="Document text has not been extracted yet. Please process the document first."
        )

    # 3. Perform chunking with user-configured chunk_size & chunk_overlap
    summary = await chunking_service.chunk_document(
        session=session,
        project_id=project_id,
        document_id=document_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return ChunkingSummaryResponse.model_validate(summary)



@router.get(
    "/{project_id}/documents/{document_id}/chunks",
    response_model=list[DocumentChunkResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Document Chunks",
    description="Retrieve all sequential structured text chunks generated for this document.",
)
async def get_document_chunks(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of chunks to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_db),
) -> list[DocumentChunkResponse]:
    """Fetch paginated sequential chunks of a document for verification and citation inspection."""
    # 1. Fetch document and verify existence
    doc = await get_document_by_id(
        session=session, project_id=project_id, document_id=document_id
    )
    if not doc:
        raise NotFoundException(
            message=f"Document with ID '{document_id}' was not found in project '{project_id}'."
        )

    # 2. Query chunks
    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .limit(limit)
        .offset(offset)
    )
    chunks = result.scalars().all()
    return [DocumentChunkResponse.model_validate(c) for c in chunks]


@router.post(
    "/{project_id}/documents/{document_id}/embed",
    response_model=EmbeddingSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Document Embeddings",
    description="Trigger batch semantic vector generation for all chunks of a processed document.",
)
async def embed_project_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> EmbeddingSummaryResponse:
    """Generate vector embeddings for all chunks of the target document."""
    summary = await embedding_service.embed_document(
        session=session,
        project_id=project_id,
        document_id=document_id,
    )
    return EmbeddingSummaryResponse.model_validate(summary)


@router.get(
    "/{project_id}/documents/{document_id}/embeddings",
    response_model=list[EmbeddingMetadataResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Document Embeddings Metadata",
    description="Retrieve generation status and metadata for all chunks of this document.",
)
async def get_document_embeddings(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of embedding metadata records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_db),
) -> list[EmbeddingMetadataResponse]:
    """Fetch paginated sequential chunk embedding metadata for debugging and RAG validation."""
    # 1. Fetch document and verify existence
    doc = await get_document_by_id(
        session=session, project_id=project_id, document_id=document_id
    )
    if not doc:
        raise NotFoundException(
            message=f"Document with ID '{document_id}' was not found in project '{project_id}'."
        )

    # 2. Query embeddings joined on document chunks
    result = await session.execute(
        select(ChunkEmbedding)
        .join(DocumentChunk, DocumentChunk.id == ChunkEmbedding.chunk_id)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .limit(limit)
        .offset(offset)
    )
    embeddings = result.scalars().all()
    return [EmbeddingMetadataResponse.model_validate(e) for e in embeddings]


@router.post(
    "/{project_id}/documents/{document_id}/index",
    response_model=IndexingSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Index Document to Qdrant",
    description="Upload semantic vector embeddings and rich payload metadata to Qdrant.",
)
async def index_project_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    qdrant_service: QdrantService = Depends(get_qdrant_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    indexing_service: VectorIndexingService = Depends(get_indexing_service),
) -> IndexingSummaryResponse:
    """Index the document chunks and embeddings into Qdrant."""
    summary = await indexing_service.index_document(
        session=session,
        project_id=project_id,
        document_id=document_id,
        qdrant_service=qdrant_service,
        embedding_service=embedding_service,
    )
    return IndexingSummaryResponse.model_validate(summary)



