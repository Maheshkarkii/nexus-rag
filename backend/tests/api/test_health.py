"""Unit and integration tests for backend health, readiness, and CORS headers."""

import httpx
import pytest
from fastapi.testclient import TestClient


def test_health_check_sync(client: TestClient) -> None:
    """Verify that GET /api/v1/health returns HTTP 200 and expected status 'ok'."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
    assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_check_async(async_client: httpx.AsyncClient) -> None:
    """Verify that asynchronous GET /api/v1/health returns HTTP 200 and status 'ok'."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data == {"status": "ok"}


def test_readiness_check_sync(client: TestClient) -> None:
    """Verify that GET /api/v1/health/ready returns appropriate status and evaluates database connectivity."""
    response = client.get("/api/v1/health/ready")
    # Endpoint returns 200 if DB is connected or 503 if unavailable (never 500 unhandled)
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert data["status"] in ("ready", "degraded")
    assert "environment" in data
    assert "version" in data
    assert "timestamp" in data
    assert "checks" in data
    assert "configuration" in data["checks"]
    assert "database" in data["checks"]
    assert data["checks"]["database"]["name"] == "postgresql"
    assert "vector_store" in data["checks"]


def test_root_endpoint(client: TestClient) -> None:
    """Verify that root endpoint GET / provides service discovery metadata and links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "AI Research Assistant"
    assert data["status"] == "running"
    assert "health" in data
    assert "ready" in data
    assert "/api/v1/health" in data["health"]
    assert "/api/v1/health/ready" in data["ready"]


def test_not_found_endpoint_error_envelope(client: TestClient) -> None:
    """Verify that accessing a non-existent route produces a standardized error envelope."""
    response = client.get("/api/v1/non-existent-endpoint")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    assert data["error"]["code"] == "NOT_FOUND"


def test_cors_headers_for_frontend_origin(client: TestClient) -> None:
    """Verify that CORS preflight and request headers allow http://localhost:3000."""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
