"""Local file storage service abstraction with streaming and path safety guarantees."""

import logging
from pathlib import Path
from typing import Optional, Tuple
import uuid
import aiofiles
from fastapi import UploadFile
from app.core.config import get_settings
from app.core.exceptions import BadRequestException

logger = logging.getLogger("ai_research_assistant.storage")

CHUNK_SIZE = 64 * 1024  # 64 KB streaming buffer


class StorageService:
    """Manages file storage operations organized by project workspace with path security."""

    def __init__(self, storage_root: Optional[Path] = None) -> None:
        settings = get_settings()
        self.storage_root = (storage_root or settings.storage_directory).resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def get_project_directory(self, project_id: uuid.UUID) -> Path:
        """Resolve and create the project storage directory with path traversal guards."""
        target_dir = (self.storage_root / "projects" / str(project_id)).resolve()
        if not target_dir.is_relative_to(self.storage_root):
            raise BadRequestException(message="Invalid storage path detected.")
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def resolve_safe_path(self, storage_path: str) -> Path:
        """Resolve relative storage path and verify it remains inside the storage root."""
        clean_relative = storage_path.lstrip("/\\")
        abs_path = (self.storage_root / clean_relative).resolve()
        if not abs_path.is_relative_to(self.storage_root):
            raise BadRequestException(message="Path traversal attempt detected.")
        return abs_path

    async def save_file(
        self,
        project_id: uuid.UUID,
        upload_file: UploadFile,
        stored_filename: str,
        max_size_bytes: Optional[int] = None,
    ) -> Tuple[str, int]:
        """Stream an uploaded file to disk in chunks, enforcing max file size limits."""
        settings = get_settings()
        limit_bytes = max_size_bytes or settings.max_upload_size_bytes

        project_dir = self.get_project_directory(project_id)
        destination = (project_dir / stored_filename).resolve()

        if not destination.is_relative_to(self.storage_root):
            raise BadRequestException(message="Invalid destination path.")

        total_bytes = 0
        try:
            async with aiofiles.open(destination, "wb") as out_file:
                while True:
                    chunk = await upload_file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > limit_bytes:
                        # Clean up oversized partial file immediately
                        await out_file.close()
                        if destination.exists():
                            destination.unlink(missing_ok=True)
                        limit_mb = limit_bytes // (1024 * 1024)
                        raise BadRequestException(
                            message=f"Uploaded file exceeds maximum allowed limit of {limit_mb} MB."
                        )
                    await out_file.write(chunk)
        except Exception:
            if destination.exists():
                destination.unlink(missing_ok=True)
            raise

        relative_path = f"projects/{project_id}/{stored_filename}"
        logger.info(f"Saved file {stored_filename} ({total_bytes} bytes) to {relative_path}")
        return relative_path, total_bytes

    def delete_file(self, storage_path: str) -> bool:
        """Delete physical file from disk safely, ignoring missing files."""
        try:
            target = self.resolve_safe_path(storage_path)
            if target.exists() and target.is_file():
                target.unlink(missing_ok=True)
                logger.info(f"Deleted physical file at {storage_path}")
                return True
            else:
                logger.warning(f"File at {storage_path} not found during physical deletion.")
                return False
        except Exception as e:
            logger.error(f"Error deleting physical file at {storage_path}: {e}")
            return False

    def file_exists(self, storage_path: str) -> bool:
        """Check if physical file exists on disk."""
        try:
            target = self.resolve_safe_path(storage_path)
            return target.exists() and target.is_file()
        except Exception:
            return False


# Singleton storage service instance
default_storage_service = StorageService()


def get_storage_service() -> StorageService:
    """Dependency injector for StorageService."""
    return default_storage_service
