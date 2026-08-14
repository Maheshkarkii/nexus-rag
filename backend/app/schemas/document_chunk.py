import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkingSummaryResponse(BaseModel):
    """Execution summary returned after successfully chunking a research document."""

    document_id: uuid.UUID = Field(..., description="UUID of the processed document")
    chunk_count: int = Field(..., description="Total number of chunks generated")
    total_characters: int = Field(..., description="Combined character length across all chunks")
    total_tokens: int = Field(..., description="Estimated token count across all chunks")


class DocumentChunkResponse(BaseModel):
    """Detailed representation of a single persisted document chunk for RAG inspection."""

    id: uuid.UUID = Field(..., description="Unique UUID identifier of this chunk")
    document_id: uuid.UUID = Field(..., description="UUID of the parent document")
    project_id: uuid.UUID = Field(..., description="UUID of the project workspace")
    chunk_index: int = Field(..., description="0-based sequential index of the chunk")
    text: str = Field(..., description="Normalized chunk text content")
    token_count: int = Field(..., description="Calculated token count of this chunk")
    character_count: int = Field(..., description="Character count of this chunk")
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias="metadata_",
        description="Structured citation metadata (page_number, section_title, etc.)",
    )
    created_at: datetime = Field(..., description="UTC creation timestamp")
    updated_at: datetime = Field(..., description="UTC update timestamp")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
