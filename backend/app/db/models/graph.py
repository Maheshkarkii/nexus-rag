"""SQLAlchemy models for knowledge graph entities and relationships."""

import uuid
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.db.models.project import Project
    from app.db.models.document import Document
    from app.db.models.document_chunk import DocumentChunk


class Entity(BaseModel):
    """Knowledge Graph Entity model."""

    __tablename__ = "entities"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # Paper, Model, Dataset, Method, Concept, etc.
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    aliases_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<Entity id={self.id} type='{self.entity_type}' name='{self.canonical_name}'>"


class Relationship(BaseModel):
    """Knowledge Graph Relationship model connecting entities with evidence provenance."""

    __tablename__ = "relationships"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # uses_method, evaluated_on, reports_metric, etc.
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    evidence_text: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    def __repr__(self) -> str:
        return f"<Relationship {self.source_entity_id} -[{self.relationship_type}]-> {self.target_entity_id}>"
