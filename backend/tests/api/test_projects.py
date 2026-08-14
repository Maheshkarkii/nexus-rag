"""Unit and integration tests for Research Project CRUD endpoints."""

import uuid
from fastapi.testclient import TestClient
import httpx
import pytest


def test_create_project_success(client: TestClient) -> None:
    """Verify creating a project with valid name and description returns 201 and valid UUID."""
    payload = {
        "name": "Attention & Transformer Synthesis",
        "description": "Comprehensive review of long-context LLM architectures.",
    }
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert uuid.UUID(data["id"])
    assert data["name"] == "Attention & Transformer Synthesis"
    assert data["description"] == "Comprehensive review of long-context LLM architectures."
    assert "created_at" in data
    assert "updated_at" in data


def test_create_project_without_description(client: TestClient) -> None:
    """Verify creating a project without description succeeds with description as None."""
    payload = {"name": "Healthcare Clinical Trials Review"}
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Healthcare Clinical Trials Review"
    assert data["description"] is None


def test_create_project_missing_name(client: TestClient) -> None:
    """Verify creating a project without name fails with 422 validation error."""
    payload = {"description": "Missing project name"}
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_create_project_blank_name(client: TestClient) -> None:
    """Verify creating a project with blank/whitespace-only name fails with 422."""
    payload = {"name": "   "}
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data


def test_create_project_strips_surrounding_whitespace(client: TestClient) -> None:
    """Verify leading and trailing whitespace is automatically stripped from name and description."""
    payload = {
        "name": "   Sparse Attention Models   ",
        "description": "   Investigating linear attention mechanisms.   ",
    }
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Sparse Attention Models"
    assert data["description"] == "Investigating linear attention mechanisms."


def test_list_projects_empty(client: TestClient) -> None:
    """Verify listing projects on a fresh test database returns an empty list."""
    response = client.get("/api/v1/projects")
    assert response.status_code == 200
    assert response.json() == []


def test_list_projects_ordering(client: TestClient) -> None:
    """Verify that projects are returned ordered by creation date descending (newest first)."""
    # Create first project
    res1 = client.post("/api/v1/projects", json={"name": "Project Alpha"})
    assert res1.status_code == 201
    id1 = res1.json()["id"]

    # Create second project
    res2 = client.post("/api/v1/projects", json={"name": "Project Beta"})
    assert res2.status_code == 201
    id2 = res2.json()["id"]

    # List all
    list_res = client.get("/api/v1/projects")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 2
    # Project Beta (newest) should appear first
    assert items[0]["id"] == id2
    assert items[1]["id"] == id1


def test_get_single_project_success(client: TestClient) -> None:
    """Verify retrieving an existing project by its UUID."""
    created = client.post(
        "/api/v1/projects",
        json={"name": "Financial Microstructure", "description": "High-frequency limit order books."},
    ).json()
    project_id = created["id"]

    response = client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == project_id
    assert data["name"] == "Financial Microstructure"
    assert data["description"] == "High-frequency limit order books."


def test_get_single_project_not_found(client: TestClient) -> None:
    """Verify retrieving a non-existent UUID returns 404 with structured error envelope."""
    non_existent_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/projects/{non_existent_id}")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert f"'{non_existent_id}'" in data["error"]["message"]


def test_get_single_project_invalid_uuid(client: TestClient) -> None:
    """Verify passing a malformed UUID string produces 422 validation error."""
    response = client.get("/api/v1/projects/not-a-valid-uuid")
    assert response.status_code == 422


def test_update_project_name(client: TestClient) -> None:
    """Verify partially updating a project name preserves description and updates timestamp."""
    created = client.post(
        "/api/v1/projects",
        json={"name": "Initial Name", "description": "Static Description"},
    ).json()
    project_id = created["id"]

    response = client.patch(f"/api/v1/projects/{project_id}", json={"name": "Updated Workspace Title"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == project_id
    assert data["name"] == "Updated Workspace Title"
    assert data["description"] == "Static Description"


def test_update_project_description(client: TestClient) -> None:
    """Verify partially updating a project description preserves name."""
    created = client.post(
        "/api/v1/projects",
        json={"name": "Constant Name", "description": "Initial Description"},
    ).json()
    project_id = created["id"]

    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"description": "Refined Deep Learning Synthesis."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Constant Name"
    assert data["description"] == "Refined Deep Learning Synthesis."


def test_update_project_not_found(client: TestClient) -> None:
    """Verify updating a non-existent UUID returns 404 Not Found."""
    non_existent_id = str(uuid.uuid4())
    response = client.patch(
        f"/api/v1/projects/{non_existent_id}",
        json={"name": "Ghost Project"},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "NOT_FOUND"


def test_update_project_blank_name_fails(client: TestClient) -> None:
    """Verify attempting to update name to a blank/whitespace string returns 422."""
    created = client.post("/api/v1/projects", json={"name": "Valid Title"}).json()
    project_id = created["id"]

    response = client.patch(f"/api/v1/projects/{project_id}", json={"name": "   "})
    assert response.status_code == 422


def test_delete_project_success(client: TestClient) -> None:
    """Verify deleting an existing project returns 204 No Content and removes it from the database."""
    created = client.post("/api/v1/projects", json={"name": "To Be Deleted"}).json()
    project_id = created["id"]

    # Delete
    del_res = client.delete(f"/api/v1/projects/{project_id}")
    assert del_res.status_code == 204
    assert del_res.text == ""

    # Verify subsequent GET returns 404
    get_res = client.get(f"/api/v1/projects/{project_id}")
    assert get_res.status_code == 404


def test_delete_project_not_found(client: TestClient) -> None:
    """Verify deleting a non-existent UUID returns 404 Not Found."""
    non_existent_id = str(uuid.uuid4())
    response = client.delete(f"/api/v1/projects/{non_existent_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_async_project_crud_lifecycle(async_client: httpx.AsyncClient) -> None:
    """Verify full asynchronous project lifecycle via HTTPX async client."""
    # 1. Create
    create_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Async Workspace", "description": "Testing AsyncPG session dependency"},
    )
    assert create_res.status_code == 201
    project_id = create_res.json()["id"]

    # 2. Get
    get_res = await async_client.get(f"/api/v1/projects/{project_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Async Workspace"

    # 3. Patch
    patch_res = await async_client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Async Workspace Renamed"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Async Workspace Renamed"

    # 4. Delete
    delete_res = await async_client.delete(f"/api/v1/projects/{project_id}")
    assert delete_res.status_code == 204
