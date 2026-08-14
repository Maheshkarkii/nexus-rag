"""Pydantic schemas for research documents, extraction content, and metadata."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    """Serialized document metadata response without leaking server filesystem paths."""

    id: uuid.UUID = Field(
        ...,
        description="Unique identifier (UUID v4) of the document",
        examples=["8f8e7e6d-5c4b-3a21-0987-654321fedcba"],
    )
    project_id: uuid.UUID = Field(
        ...,
        description="UUID of the parent research project workspace",
        examples=["73134438-e654-43a1-abd5-69dc90ce3bc6"],
    )
    original_filename: str = Field(
        ...,
        description="Original name of the uploaded research paper or dataset",
        examples=["attention_is_all_you_need.pdf"],
    )
    mime_type: str = Field(
        ...,
        description="Detected MIME content-type of the file",
        examples=["application/pdf"],
    )
    file_extension: str = Field(
        ...,
        description="Lower-case file extension with dot",
        examples=[".pdf"],
    )
    file_size: int = Field(
        ...,
        description="Total size in bytes",
        examples=[2201948],
    )
    status: str = Field(
        ...,
        description="Current lifecycle state: uploaded, processing, ready, failed",
        examples=["ready"],
    )
    extracted_character_count: int | None = Field(
        default=None,
        description="Total character count of extracted normalized text",
        examples=[45120],
    )
    extracted_word_count: int | None = Field(
        default=None,
        description="Total word count of extracted normalized text",
        examples=[6820],
    )
    processing_error: str | None = Field(
        default=None,
        description="Sanitized explanation if text extraction failed",
    )
    processed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when document processing was completed",
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the file was uploaded",
    )
    updated_at: datetime = Field(
        ...,
        description="UTC timestamp when the document record was last updated",
    )

    model_config = ConfigDict(from_attributes=True)


class DocumentContentResponse(BaseModel):
    """Detailed content response including extracted normalized text for verification and preview."""

    id: uuid.UUID = Field(..., description="Document UUID")
    project_id: uuid.UUID = Field(..., description="Parent project UUID")
    original_filename: str = Field(..., description="Original uploaded filename")
    mime_type: str = Field(..., description="MIME content-type")
    file_extension: str = Field(..., description="File extension")
    file_size: int = Field(..., description="File size in bytes")
    status: str = Field(..., description="Processing status: uploaded, processing, ready, failed")
    extracted_text: str | None = Field(
        default=None,
        description="Normalized extracted textual content ready for Stage 10 chunking",
    )
    extracted_character_count: int | None = Field(default=None)
    extracted_word_count: int | None = Field(default=None)
    extracted_metadata: dict[str, Any] | None = Field(default=None)
    processing_error: str | None = Field(default=None)
    processed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)

    model_config = ConfigDict(from_attributes=True)
