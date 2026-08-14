"""Common Pydantic data schemas and standardized response models."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness probe response model."""

    status: str = Field(
        default="healthy",
        description="Process operational status",
        examples=["healthy"],
    )


class DependencyCheck(BaseModel):
    """Individual infrastructure or component readiness status."""

    name: str = Field(..., description="Name of the evaluated component or dependency")
    status: str = Field(..., description="Component state (e.g. ready, unconfigured, pending)")
    details: str | None = Field(
        default=None,
        description="Informational message regarding check status or stage limitation",
    )


class ReadinessResponse(BaseModel):
    """Readiness probe response model verifying operational state."""

    status: str = Field(
        default="ready",
        description="Overall service readiness status",
        examples=["ready"],
    )
    environment: str = Field(
        ...,
        description="Active application runtime environment",
        examples=["development"],
    )
    version: str = Field(
        ...,
        description="Application version",
        examples=["0.1.0"],
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="UTC timestamp of readiness evaluation",
    )
    checks: dict[str, DependencyCheck] = Field(
        default_factory=dict,
        description="Subsystem check results",
    )


class ErrorDetail(BaseModel):
    """Structured error payload details."""

    code: str = Field(..., description="Machine-readable error classification code")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: Any | None = Field(
        default=None,
        description="Optional granular error metadata or validation field details",
    )


class ErrorResponse(BaseModel):
    """Standardized top-level API error envelope."""

    error: ErrorDetail = Field(..., description="Error payload details")


class ServiceInfoResponse(BaseModel):
    """Service discovery and root metadata model."""

    name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Active runtime environment")
    status: str = Field(default="running", description="Process execution status")
    health: str = Field(..., description="Path to liveness health endpoint")
    ready: str = Field(..., description="Path to readiness health endpoint")
    docs: str = Field(..., description="Path to interactive API documentation")
