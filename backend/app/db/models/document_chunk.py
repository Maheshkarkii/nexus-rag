"""SQLAlchemy model for document chunks, token counts, and rich citation metadata."""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
import uuid
from sqlalchemy import ForeignKey, Index, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.db.models.document import Document
    from app.db.models.project import Project
    from app.db.models.embedding import ChunkEmbedding


class DocumentChunk(BaseModel):
    """Represents a discrete, contextual slice of text extracted from a research document."""

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent document",
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        doc="Foreign key reference to parent project workspace for tenant isolation",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="0-based deterministic sequential index within the document",
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Normalized chunk text content ready for downstream embedding",
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Calculated token count of this chunk",
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Character length of chunk text",
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        doc="Source metadata (page_number, page_start, page_end, section_title, section_path, sheet_name, row_start, row_end, json_path)",
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )
    embedding: Mapped[Optional["ChunkEmbedding"]] = relationship(
        "ChunkEmbedding",
        back_populates="chunk",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
        doc="The generated vector embedding for this chunk",
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_doc_index"),
        Index("ix_document_chunks_project_id", "project_id"),
        Index("ix_document_chunks_doc_index", "document_id", "chunk_index"),
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} doc={self.document_id} idx={self.chunk_index} tokens={self.token_count}>"
