"""SQLAlchemy model for research projects and workspaces."""

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation
    from app.db.models.document import Document
    from app.db.models.report import Report


class Project(BaseModel):
    """Represents an isolated research project or workspace for organizing documents and queries."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="User-facing title or name of the research project workspace",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional detailed description or objective of the research project",
    )

    # Relationships
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="Collection of uploaded documents belonging to this research workspace",
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="Collection of active research sessions belonging to this project workspace",
    )

    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
        doc="Collection of generated research reports belonging to this project workspace",
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name='{self.name}'>"
