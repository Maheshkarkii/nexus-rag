"""SQLAlchemy model for research reports and document generation."""

import uuid
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.db.models.project import Project
    from app.db.models.conversation import Conversation


class Report(BaseModel):
    """Report model storing structured research report metadata, content sections, citations, and versioning."""

    __tablename__ = "reports"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, default="research_summary", index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generating", index=True) # draft, generating, completed, failed
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="reports", lazy="raise")
    conversation: Mapped[Optional["Conversation"]] = relationship("Conversation", lazy="raise")

    def __repr__(self) -> str:
        return f"<Report id={self.id} title='{self.title}' type='{self.report_type}' version={self.version} status='{self.status}'>"
