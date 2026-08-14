import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class RetrievalRequest(BaseModel):
    """Input payload for execution of semantic query retrieval scoped to a project."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query string to embed and run similarity matching on",
    )
    top_k: int = Field(
        5,
        ge=1,
        le=100,
        description="Maximum number of relevant chunks to return",
    )
    score_threshold: Optional[float] = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold to include a chunk in outcomes",
    )
    document_ids: Optional[List[uuid.UUID]] = Field(
        None,
        description="Optional list of document UUIDs to filter results within",
    )
    file_types: Optional[List[str]] = Field(
        None,
        description="Optional list of file extensions (e.g. .pdf, .txt) to narrow search scope",
    )

    @field_validator("query")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Query string cannot be empty or whitespace only.")
        return value


class RetrievalResultResponse(BaseModel):
    """Structured evidence chunk retrieved from the vector store."""

    chunk_id: uuid.UUID = Field(..., description="UUID of the DocumentChunk source")
    document_id: uuid.UUID = Field(..., description="UUID of the parent Document")
    project_id: uuid.UUID = Field(..., description="UUID of the parent Project")
    text: str = Field(..., description="Raw text segment of the chunk")
    score: float = Field(..., description="Calculated primary relevance coefficient score")
    vector_score: Optional[float] = Field(None, description="Raw semantic vector similarity score")
    reranker_score: Optional[float] = Field(None, description="Calculated cross-encoder model relevance score")
    chunk_index: int = Field(..., description="Index order value of the chunk within the document")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Associated structured file headers, positions, and tags",
    )


class RetrievalResponse(BaseModel):
    """Top-level collection returned by the semantic query pipeline."""

    query: str = Field(..., description="Echo of the input query string")
    results: List[RetrievalResultResponse] = Field(
        ...,
        description="Descending sorted list of semantically matching chunks",
    )
