"""Unit and integration tests for research document upload and metadata API endpoints."""

import io
import uuid
from fastapi.testclient import TestClient
import httpx
import pytest


def create_sample_project(client: TestClient) -> str:
    """Helper fixture to create a valid research project workspace."""
    res = client.post("/api/v1/projects", json={"name": "Sample Workspace"})
    assert res.status_code == 201
    return res.json()["id"]


def test_upload_valid_pdf_document(client: TestClient) -> None:
    """Verify uploading a valid PDF returns 201 Created and correct metadata."""
    project_id = create_sample_project(client)
    file_content = b"%PDF-1.5 \n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"

    response = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("attention_paper.pdf", io.BytesIO(file_content), "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert uuid.UUID(data["id"])
    assert data["project_id"] == project_id
    assert data["original_filename"] == "attention_paper.pdf"
    assert data["file_extension"] == ".pdf"
    assert data["file_size"] == len(file_content)
    assert data["status"] == "uploaded"
    assert "created_at" in data
    assert "updated_at" in data


def test_upload_valid_supported_formats(client: TestClient) -> None:
    """Verify all supported extensions (.docx, .txt, .csv, .xlsx, .json) upload successfully."""
    project_id = create_sample_project(client)
    formats = [
        ("notes.docx", b"PK\x03\x04docx_mock_bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
        ("protocol.txt", b"Research Protocol Step 1", "text/plain", ".txt"),
        ("dataset.csv", b"id,val,score\n1,alpha,0.95\n2,beta,0.88", "text/csv", ".csv"),
        ("metrics.xlsx", b"PK\x03\x04xlsx_mock_bytes", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
        ("schema.json", b'{"research_topic": "sparse_attention"}', "application/json", ".json"),
    ]

    for filename, content, mime, expected_ext in formats:
        response = client.post(
            f"/api/v1/projects/{project_id}/documents",
            files={"file": (filename, io.BytesIO(content), mime)},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["original_filename"] == filename
        assert data["file_extension"] == expected_ext
        assert data["file_size"] == len(content)
        assert data["status"] == "uploaded"


def test_upload_unsupported_file_extension_fails(client: TestClient) -> None:
    """Verify uploading an unsupported extension (e.g. .exe, .sh) returns 400 Bad Request."""
    project_id = create_sample_project(client)
    response = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("malicious.exe", io.BytesIO(b"MZ\x90\x00executable"), "application/x-msdownload")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "BAD_REQUEST"
    assert "Unsupported file type" in data["error"]["message"]


def test_upload_to_nonexistent_project_fails(client: TestClient) -> None:
    """Verify uploading to a non-existent project returns 404 Not Found."""
    random_project_id = str(uuid.uuid4())
    response = client.post(
        f"/api/v1/projects/{random_project_id}/documents",
        files={"file": ("paper.pdf", io.BytesIO(b"%PDF-1.4 sample"), "application/pdf")},
    )
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "NOT_FOUND"


def test_duplicate_filenames_allowed(client: TestClient) -> None:
    """Verify uploading files with identical original filenames creates distinct document records."""
    project_id = create_sample_project(client)
    content1 = b"%PDF-1.4 Version 1"
    content2 = b"%PDF-1.4 Version 2"

    res1 = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("study.pdf", io.BytesIO(content1), "application/pdf")},
    )
    assert res1.status_code == 201
    doc1 = res1.json()

    res2 = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("study.pdf", io.BytesIO(content2), "application/pdf")},
    )
    assert res2.status_code == 201
    doc2 = res2.json()

    assert doc1["id"] != doc2["id"]
    assert doc1["original_filename"] == doc2["original_filename"] == "study.pdf"


def test_list_project_documents_ordering(client: TestClient) -> None:
    """Verify listing documents returns records in created_at descending order."""
    project_id = create_sample_project(client)

    # Initially empty
    empty_res = client.get(f"/api/v1/projects/{project_id}/documents")
    assert empty_res.status_code == 200
    assert empty_res.json() == []

    # Upload Doc 1
    res1 = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("doc_1.txt", io.BytesIO(b"Doc 1"), "text/plain")},
    )
    id1 = res1.json()["id"]

    # Upload Doc 2
    res2 = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("doc_2.txt", io.BytesIO(b"Doc 2"), "text/plain")},
    )
    id2 = res2.json()["id"]

    # List all
    list_res = client.get(f"/api/v1/projects/{project_id}/documents")
    assert list_res.status_code == 200
    docs = list_res.json()
    assert len(docs) == 2
    assert docs[0]["id"] == id2
    assert docs[1]["id"] == id1


def test_get_single_document_metadata(client: TestClient) -> None:
    """Verify retrieving document metadata by ID."""
    project_id = create_sample_project(client)
    uploaded = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("survey.pdf", io.BytesIO(b"%PDF-1.5 Survey"), "application/pdf")},
    ).json()
    doc_id = uploaded["id"]

    res = client.get(f"/api/v1/projects/{project_id}/documents/{doc_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == doc_id
    assert data["original_filename"] == "survey.pdf"


def test_get_document_cross_project_isolation(client: TestClient) -> None:
    """Verify accessing a document belonging to project A using project B's URL returns 404."""
    project_a = create_sample_project(client)
    project_b = create_sample_project(client)

    uploaded = client.post(
        f"/api/v1/projects/{project_a}/documents",
        files={"file": ("project_a_secret.pdf", io.BytesIO(b"%PDF-1.5 Secret"), "application/pdf")},
    ).json()
    doc_id = uploaded["id"]

    # Try fetching project A's document via project B URL
    res = client.get(f"/api/v1/projects/{project_b}/documents/{doc_id}")
    assert res.status_code == 404


def test_delete_document_success(client: TestClient) -> None:
    """Verify deleting a document removes the database record and returns 204 No Content."""
    project_id = create_sample_project(client)
    uploaded = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("to_delete.txt", io.BytesIO(b"Delete me"), "text/plain")},
    ).json()
    doc_id = uploaded["id"]

    # Delete
    del_res = client.delete(f"/api/v1/projects/{project_id}/documents/{doc_id}")
    assert del_res.status_code == 204

    # Subsequent GET returns 404
    get_res = client.get(f"/api/v1/projects/{project_id}/documents/{doc_id}")
    assert get_res.status_code == 404


def test_delete_document_not_found(client: TestClient) -> None:
    """Verify deleting a non-existent document returns 404 Not Found."""
    project_id = create_sample_project(client)
    random_doc_id = str(uuid.uuid4())
    res = client.delete(f"/api/v1/projects/{project_id}/documents/{random_doc_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_async_document_upload_lifecycle(async_client: httpx.AsyncClient) -> None:
    """Verify asynchronous document upload, retrieval, and deletion lifecycle."""
    # 1. Create project
    p_res = await async_client.post("/api/v1/projects", json={"name": "Async Ingestion Project"})
    assert p_res.status_code == 201
    project_id = p_res.json()["id"]

    # 2. Upload file
    upload_res = await async_client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("experiment_data.json", b'{"loss": 0.124, "val_acc": 0.982}', "application/json")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 3. Retrieve metadata
    get_res = await async_client.get(f"/api/v1/projects/{project_id}/documents/{doc_id}")
    assert get_res.status_code == 200
    assert get_res.json()["original_filename"] == "experiment_data.json"

    # 4. Delete
    del_res = await async_client.delete(f"/api/v1/projects/{project_id}/documents/{doc_id}")
    assert del_res.status_code == 204
