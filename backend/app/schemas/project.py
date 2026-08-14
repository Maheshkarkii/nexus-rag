"""Pydantic request and response schemas for research projects."""

from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectBase(BaseModel):
    """Base attributes shared across project schemas."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User-facing title or name of the research project workspace",
        examples=["Attention & Transformer Synthesis"],
    )
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Optional detailed description or research goals for the project",
        examples=["Comparative review of long-context LLM architectures."],
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_and_strip_name(cls, value: str) -> str:
        """Ensure project name is not blank and strip surrounding whitespace."""
        if not isinstance(value, str):
            raise ValueError("Project name must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("Project name cannot be blank or whitespace-only")
        return stripped

    @field_validator("description", mode="before")
    @classmethod
    def validate_and_strip_description(cls, value: Optional[str]) -> Optional[str]:
        """Strip surrounding whitespace on description and convert empty strings to None."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Project description must be a string")
        stripped = value.strip()
        return stripped if stripped else None


class ProjectCreate(ProjectBase):
    """Request payload schema for creating a new research project."""
    pass


class ProjectUpdate(BaseModel):
    """Request payload schema for updating an existing research project."""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated project title",
        examples=["Updated Deep Learning Review"],
    )
    description: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Updated project description",
        examples=["Refined scope focusing exclusively on sparse attention."],
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_and_strip_update_name(cls, value: Optional[str]) -> Optional[str]:
        """Validate non-blank name when provided for update."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Project name must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("Project name cannot be blank or whitespace-only")
        return stripped

    @field_validator("description", mode="before")
    @classmethod
    def validate_and_strip_update_description(cls, value: Optional[str]) -> Optional[str]:
        """Strip description string when provided for update."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Project description must be a string")
        stripped = value.strip()
        return stripped if stripped else None


class ProjectResponse(ProjectBase):
    """Response schema returning serialized research project metadata."""

    id: uuid.UUID = Field(
        ...,
        description="Unique identifier (UUID v4) of the research project",
        examples=["73134438-e654-43a1-abd5-69dc90ce3bc6"],
    )
    created_at: datetime = Field(
        ...,
        description="UTC creation timestamp with timezone information",
    )
    updated_at: datetime = Field(
        ...,
        description="UTC timestamp of last modification with timezone information",
    )

    model_config = ConfigDict(from_attributes=True)
