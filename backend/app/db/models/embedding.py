"""SQLAlchemy model for chunk embeddings, storing raw vectors and model metadata."""

import uuid
from typing import Optional
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel


class ChunkEmbedding(BaseModel):
    """Represents the semantic vector embedding generated for a specific document chunk."""

    __tablename__ = "chunk_embeddings"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # Enforce at most one embedding per chunk
        index=True,
        doc="Foreign key reference to parent document chunk",
    )
    model_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Name of the embedding model used (e.g. sentence-transformers/all-MiniLM-L6-v2)",
    )
    dimension: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Dimensionality of the embedding vector",
    )
    vector: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        doc="The floating point vector array representing the chunk semantic space",
    )
    normalized: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether the embedding vector is L2 normalized",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        doc="Current embedding generation state: pending, completed, failed",
    )
    processing_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Sanitized error description if embedding generation fails",
    )

    # Relationships
    chunk: Mapped["DocumentChunk"] = relationship(
        "DocumentChunk",
        back_populates="embedding",
    )

    def __repr__(self) -> str:
        return f"<ChunkEmbedding id={self.id} chunk={self.chunk_id} model='{self.model_name}' dim={self.dimension}>"
