from typing import Optional, TYPE_CHECKING
import uuid
from sqlalchemy import ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.db.models.conversation import Conversation


class Message(BaseModel):
    """Represents a single message exchange (user query or assistant response) inside a conversation."""

    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(50),  # user, assistant, system
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Optional metadata containing sources, citations, model configurations, and latency metrics",
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} role='{self.role}'>"
