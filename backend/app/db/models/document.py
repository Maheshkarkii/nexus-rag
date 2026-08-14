"""SQLAlchemy model for research documents and uploaded file metadata."""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
import uuid
from sqlalchemy import BigInteger, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel, UTCDateTime

if TYPE_CHECKING:
    from app.db.models.project import Project
    from app.db.models.document_chunk import DocumentChunk


class Document(BaseModel):
    """Represents uploaded file metadata and extracted content belonging to a research workspace."""

    __tablename__ = "documents"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key reference to parent research project workspace",
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Original filename as uploaded by the user",
    )
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        doc="Server-generated unique filename preventing collisions and path traversal",
    )
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Relative filesystem path within the configured storage directory",
    )
    mime_type: Mapped[str] = mapped_column(
        String(127),
        nullable=False,
        doc="Detected MIME content-type of the file",
    )
    file_extension: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Lower-case extension including dot (e.g. .pdf, .docx, .csv)",
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="Total file size in bytes",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uploaded",
        index=True,
        doc="Current lifecycle state: uploaded, processing, ready, failed",
    )

    # --------------------------------------------------------------------------
    # Stage 9: Extracted Text Content & Ingestion Metadata
    # --------------------------------------------------------------------------
    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Normalized extracted textual content ready for downstream chunking",
    )
    extracted_character_count: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        doc="Total character count of the normalized extracted text",
    )
    extracted_word_count: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        doc="Total word count of the normalized extracted text",
    )
    extracted_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Structured metadata such as page counts, sheet headers, or row statistics",
    )
    processing_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Sanitized human-readable error explanation if extraction fails",
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
        doc="UTC timestamp when extraction pipeline completed",
    )
    indexing_status: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        default="pending",
        doc="Current Qdrant vector store indexing state: pending, indexing, indexed, failed",
    )
    indexed_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
        doc="UTC timestamp when indexing pipeline completed",
    )
    indexing_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Sanitized error description if indexing fails",
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="documents",
    )
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
        lazy="selectin",
        doc="Sequential structured text chunks generated for this document",
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} project_id={self.project_id} filename='{self.original_filename}' status='{self.status}'>"
