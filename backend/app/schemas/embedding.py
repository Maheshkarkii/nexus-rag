import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingSummaryResponse(BaseModel):
    """Serialization model representing the outcome of document embedding pipeline execution."""

    document_id: uuid.UUID = Field(..., description="UUID of the processed document")
    chunk_count: int = Field(..., description="Total number of chunks evaluated")
    embedded_count: int = Field(..., description="Number of successfully embedded chunks")
    failed_count: int = Field(..., description="Number of failed chunk embeddings")
    model_name: str = Field(..., description="Identity name of the sentence-transformer used")
    dimension: int = Field(..., description="Outbound vector coordinate space dimensionality")
    device: str = Field(..., description="Hardware processing target device (cpu/cuda)")


class EmbeddingMetadataResponse(BaseModel):
    """Lightweight metadata serializer for inspecting chunk embedding state without loading full float vectors."""

    id: uuid.UUID = Field(..., description="Unique UUID identifier of this embedding record")
    chunk_id: uuid.UUID = Field(..., description="Reference UUID to the source DocumentChunk")
    model_name: str = Field(..., description="Embedding model name used")
    dimension: int = Field(..., description="Vector dimensionality length")
    status: str = Field(..., description="Status flag: pending, completed, failed")
    created_at: datetime = Field(..., description="UTC timestamp of embedding creation")
    updated_at: datetime = Field(..., description="UTC timestamp of last update")

    model_config = ConfigDict(from_attributes=True)
