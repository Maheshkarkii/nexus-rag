"""Database access layer: engine, session management, declarative base, and models."""

from app.db.base import Base, BaseModel, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.project import Project
from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.embedding import ChunkEmbedding
from app.db.session import (
    async_session_factory,
    check_database_connection,
    engine,
    get_db,
)

__all__ = [
    "Base",
    "BaseModel",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "Project",
    "Document",
    "DocumentChunk",
    "ChunkEmbedding",
    "async_session_factory",
    "check_database_connection",
    "engine",
    "get_db",
]
