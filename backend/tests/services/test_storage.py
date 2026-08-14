"""Unit tests for local StorageService streaming, size limits, and path traversal security."""

import io
from pathlib import Path
import tempfile
import uuid
from fastapi import UploadFile
import pytest
from app.core.exceptions import BadRequestException
from app.services.storage import StorageService


@pytest.fixture
def isolated_storage() -> StorageService:
    """Create StorageService backed by a clean temporary directory."""
    temp_dir = Path(tempfile.mkdtemp(prefix="storage_test_"))
    return StorageService(storage_root=temp_dir)


@pytest.mark.asyncio
async def test_storage_save_and_delete_file(isolated_storage: StorageService) -> None:
    """Verify storing a file creates the project directory and returns relative path."""
    project_id = uuid.uuid4()
    content = b"Research Paper Binary Content"
    upload = UploadFile(filename="test.pdf", file=io.BytesIO(content))

    rel_path, file_size = await isolated_storage.save_file(
        project_id=project_id,
        upload_file=upload,
        stored_filename="safe_file.pdf",
    )

    assert rel_path == f"projects/{project_id}/safe_file.pdf"
    assert file_size == len(content)
    assert isolated_storage.file_exists(rel_path)

    # Delete
    deleted = isolated_storage.delete_file(rel_path)
    assert deleted is True
    assert not isolated_storage.file_exists(rel_path)


@pytest.mark.asyncio
async def test_storage_enforces_size_limit(isolated_storage: StorageService) -> None:
    """Verify exceeding max_size_bytes raises BadRequestException and cleans up partial file."""
    project_id = uuid.uuid4()
    oversized_content = b"A" * 1024 * 1024 * 2  # 2 MB
    upload = UploadFile(filename="large.pdf", file=io.BytesIO(oversized_content))

    with pytest.raises(BadRequestException) as exc_info:
        await isolated_storage.save_file(
            project_id=project_id,
            upload_file=upload,
            stored_filename="large.pdf",
            max_size_bytes=1024 * 1024,  # 1 MB limit
        )

    assert "exceeds maximum allowed limit" in str(exc_info.value.message)
    assert not isolated_storage.file_exists(f"projects/{project_id}/large.pdf")


def test_storage_path_traversal_detection(isolated_storage: StorageService) -> None:
    """Verify attempting to resolve path traversal outside storage root raises BadRequestException."""
    with pytest.raises(BadRequestException):
        isolated_storage.resolve_safe_path("../../etc/passwd")
