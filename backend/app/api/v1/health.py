"""Health check endpoints for container readiness, liveness, and status verification."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Standard health check response model."""

    status: str = Field(default="healthy", description="Current service operational status")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Check the operational status of the AI Research Assistant FastAPI backend service.",
)
async def get_health() -> HealthResponse:
    """Return healthy status for service monitoring and container health checks."""
    return HealthResponse(status="healthy")
