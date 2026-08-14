from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    """Payload to start a new multi-turn conversation session."""

    title: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional custom title for the research conversation session",
    )


class ConversationResponse(BaseModel):
    """Serializes a conversation session record."""

    id: uuid.UUID = Field(..., description="Unique UUID identifier of the session")
    project_id: uuid.UUID = Field(..., description="UUID of the parent research project")
    title: str = Field(..., description="User-facing title of the conversation session")
    created_at: datetime = Field(..., description="Creation UTC timestamp")
    updated_at: datetime = Field(..., description="Last updated UTC timestamp")

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """Serializes a single dialogue turn message history within a conversation."""

    id: uuid.UUID = Field(..., description="Unique message UUID identifier")
    conversation_id: uuid.UUID = Field(..., description="UUID of the parent conversation")
    role: str = Field(..., description="Dialogue role (user, assistant, system)")
    content: str = Field(..., description="Factual text contents of the message turn")
    created_at: datetime = Field(..., description="Creation UTC timestamp")
    metadata_json: Optional[dict] = Field(
        None,
        description="Optional structured metadata (sources, citations, latencies)",
    )

    model_config = ConfigDict(from_attributes=True)
