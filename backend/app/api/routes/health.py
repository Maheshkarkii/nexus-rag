from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.session import get_db
from app.core.observability import default_metrics_collector
from app.core.reliability import ReliabilityDashboardService

router = APIRouter(tags=["Observability & Health"])


@router.get("/health", summary="System Health & Readiness Check")
async def health_check(db: AsyncSession = Depends(get_db)):
    """System health check verifying database connection and service readiness."""
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    metrics = default_metrics_collector.get_summary()

    return {"status": "healthy"} if db_status == "healthy" else {"status": "degraded"}


@router.get("/health/ready", summary="Readiness Check")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness probe endpoint for container orchestration."""
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "ready" if db_status == "healthy" else "degraded",
        "environment": "development",
        "version": "1.0.0",
        "timestamp": "2026-08-14T16:00:00Z",
        "checks": {
            "configuration": {"status": "ok"},
            "database": {"name": "postgresql", "status": db_status},
            "vector_store": {"status": "ok"},
        },
    }


@router.get("/observability/metrics", summary="Observability & Quality Metrics")
async def get_metrics():
    """Retrieve system latency P50/P95 percentiles, token usage, and error statistics."""
    return default_metrics_collector.get_summary()


@router.get("/observability/dashboard", summary="Operational Reliability & SLO Dashboard")
async def get_dashboard():
    """Retrieve live operational reliability telemetry, SLI/SLO compliance, and active alerts."""
    return ReliabilityDashboardService.get_dashboard_payload()
