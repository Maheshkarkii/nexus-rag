"""Central master API router registering versioned application endpoints."""

from fastapi import APIRouter

from app.api.routes.conversations import router as conversations_router
from app.api.routes.documents import router as documents_router
from app.api.routes.graph import router as graph_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.memory import router as memory_router
from app.api.routes.projects import router as projects_router
from app.api.routes.reports import router as reports_router

api_router = APIRouter()

# ------------------------------------------------------------------------------
# Active v1 Route Registrations
# ------------------------------------------------------------------------------
# Mount health and readiness endpoints under /api/v1
api_router.include_router(health_router, prefix="", tags=["health"])

# Mount research project management endpoints under /api/v1/projects
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])

# Mount research document management endpoints under /api/v1/projects/{project_id}/documents
api_router.include_router(documents_router, prefix="/projects", tags=["documents"])

# Mount conversation sessions and message history endpoints
api_router.include_router(conversations_router, prefix="", tags=["conversations"])

# Mount research report generation and export endpoints
api_router.include_router(reports_router, prefix="", tags=["reports"])

# Mount background processing jobs endpoints
api_router.include_router(jobs_router, prefix="", tags=["jobs"])

# Mount persistent workspace memory endpoints
api_router.include_router(memory_router, prefix="", tags=["memory"])

# Mount Knowledge Graph endpoints
api_router.include_router(graph_router, prefix="", tags=["graph"])
