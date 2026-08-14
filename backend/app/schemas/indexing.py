import uuid

from pydantic import BaseModel, Field


class IndexingSummaryResponse(BaseModel):
    """Execution summary returned after successfully uploading document vectors to Qdrant."""

    document_id: uuid.UUID = Field(..., description="UUID of the indexed document")
    chunk_count: int = Field(..., description="Total number of document chunks evaluated")
    indexed_count: int = Field(..., description="Number of points successfully upserted into Qdrant")
    failed_count: int = Field(..., description="Number of points failed to upsert")
    collection_name: str = Field(..., description="Qdrant collection target name")
