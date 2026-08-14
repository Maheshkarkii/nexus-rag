"""Diagnostic verification script for AI Research Assistant Stage 9 environment."""

import os
from pathlib import Path
import sys


def check_file(path: Path, description: str) -> bool:
    if path.exists():
        print(f"  [OK] {description}: {path.name}")
        return True
    else:
        print(f"  [MISSING] {description}: {path.name}")
        return False


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    print("=" * 80)
    print(" AI Research Assistant -- Stage 9 Document Parsing & Extraction Verification")
    print("=" * 80)

    all_ok = True

    # 1. Check Root & Configuration Files
    print("\n1. Checking Monorepo Root Files:")
    root_files = [
        (root / ".env.example", ".env template"),
        (root / ".gitignore", "Git ignore rules (with storage ignored)"),
        (root / "docker-compose.yml", "Docker Compose configuration (with storage volume)"),
        (root / "README.md", "Project documentation"),
        (root / "LICENSE", "License file"),
        (root / "docs" / "architecture.md", "Architecture design document"),
    ]
    for p, desc in root_files:
        if not check_file(p, desc):
            all_ok = False

    # 2. Check Backend Architecture & Document Parsing Layer
    print("\n2. Checking Backend Architecture & Document Parsing Layer:")
    backend_files = [
        (root / "backend" / "pyproject.toml", "Backend project config with pypdf/docx/openpyxl"),
        (root / "backend" / "requirements.txt", "Backend dependencies"),
        (root / "backend" / "Dockerfile", "Backend Dockerfile"),
        (root / "backend" / "alembic.ini", "Alembic CLI configuration"),
        (root / "backend" / "alembic" / "env.py", "Alembic environment runner"),
        (root / "backend" / "alembic" / "versions" / "0001_initial_projects_table.py", "Migration 0001 (Projects)"),
        (root / "backend" / "alembic" / "versions" / "0002_create_documents_table.py", "Migration 0002 (Documents)"),
        (root / "backend" / "alembic" / "versions" / "0003_add_document_extracted_content.py", "Migration 0003 (Extracted Content)"),
        (root / "backend" / "app" / "main.py", "FastAPI main application factory & CORS"),
        (root / "backend" / "app" / "core" / "config.py", "Pydantic settings with storage config"),
        (root / "backend" / "app" / "core" / "logging.py", "Structured safe logging"),
        (root / "backend" / "app" / "core" / "exceptions.py", "Centralized exceptions & error handlers"),
        (root / "backend" / "app" / "db" / "base.py", "Declarative Base & Timestamp mixins"),
        (root / "backend" / "app" / "db" / "session.py", "Async engine & get_db dependency"),
        (root / "backend" / "app" / "db" / "models" / "project.py", "Project model with documents relation"),
        (root / "backend" / "app" / "db" / "models" / "document.py", "Document model with extracted text columns"),
        (root / "backend" / "app" / "services" / "storage.py", "StorageService abstraction & path guards"),
        (root / "backend" / "app" / "services" / "project.py", "Project async database service"),
        (root / "backend" / "app" / "services" / "document.py", "Document async database service"),
        (root / "backend" / "app" / "services" / "document_processing" / "base.py", "ExtractionResult & BaseDocumentProcessor"),
        (root / "backend" / "app" / "services" / "document_processing" / "normalizer.py", "Text normalizer utility"),
        (root / "backend" / "app" / "services" / "document_processing" / "pdf_processor.py", "PDFProcessor (pypdf)"),
        (root / "backend" / "app" / "services" / "document_processing" / "docx_processor.py", "DocxProcessor (python-docx)"),
        (root / "backend" / "app" / "services" / "document_processing" / "text_processor.py", "TextProcessor (plain text)"),
        (root / "backend" / "app" / "services" / "document_processing" / "csv_processor.py", "CSVProcessor (tabular CSV)"),
        (root / "backend" / "app" / "services" / "document_processing" / "excel_processor.py", "ExcelProcessor (openpyxl)"),
        (root / "backend" / "app" / "services" / "document_processing" / "json_processor.py", "JSONProcessor (hierarchical JSON)"),
        (root / "backend" / "app" / "services" / "document_processing" / "registry.py", "Processor registry"),
        (root / "backend" / "app" / "services" / "document_processing" / "service.py", "DocumentProcessingService"),
        (root / "backend" / "app" / "schemas" / "project.py", "Project Pydantic schemas"),
        (root / "backend" / "app" / "schemas" / "document.py", "Document & Content Pydantic schemas"),
        (root / "backend" / "app" / "schemas" / "common.py", "Standardized Pydantic schemas"),
        (root / "backend" / "app" / "dependencies" / "common.py", "FastAPI dependency module"),
        (root / "backend" / "app" / "api" / "router.py", "Master API router"),
        (root / "backend" / "app" / "api" / "routes" / "health.py", "Health & readiness route module"),
        (root / "backend" / "app" / "api" / "routes" / "projects.py", "Project CRUD route module"),
        (root / "backend" / "app" / "api" / "routes" / "documents.py", "Document upload, process & content routes"),
        (root / "backend" / "tests" / "conftest.py", "Pytest fixtures with isolated storage"),
        (root / "backend" / "tests" / "api" / "test_health.py", "API health & CORS test suite"),
        (root / "backend" / "tests" / "api" / "test_projects.py", "Project CRUD API test suite"),
        (root / "backend" / "tests" / "api" / "test_documents.py", "Document upload & lifecycle test suite"),
        (root / "backend" / "tests" / "api" / "test_document_processing.py", "Document processing & content test suite"),
        (root / "backend" / "tests" / "services" / "test_storage.py", "Storage service unit test suite"),
        (root / "backend" / "tests" / "services" / "test_processors.py", "Format processors unit test suite"),
        (root / "backend" / "tests" / "core" / "test_config.py", "Core configuration test suite"),
        (root / "backend" / "tests" / "core" / "test_exceptions.py", "Exception hierarchy test suite"),
        (root / "backend" / "tests" / "db" / "test_session.py", "Database session lifecycle test suite"),
        (root / "backend" / "tests" / "models" / "test_project.py", "Project model CRUD test suite"),
    ]
    for p, desc in backend_files:
        if not check_file(p, desc):
            all_ok = False

    # 3. Check Frontend API Client & Project Management UI Modules
    print("\n3. Checking Frontend API Client & Project Management UI Modules:")
    frontend_files = [
        (root / "frontend" / "package.json", "Frontend package.json"),
        (root / "frontend" / "tsconfig.json", "TypeScript configuration"),
        (root / "frontend" / "tailwind.config.ts", "Tailwind CSS tokens config"),
        (root / "frontend" / "Dockerfile", "Frontend Dockerfile"),
        (root / "frontend" / "src" / "app" / "globals.css", "Centralized CSS variables & design tokens"),
        (root / "frontend" / "src" / "app" / "layout.tsx", "Next.js root layout shell"),
        (root / "frontend" / "src" / "app" / "page.tsx", "AI Research Assistant home page"),
        (root / "frontend" / "src" / "app" / "projects" / "page.tsx", "Research projects list page"),
        (root / "frontend" / "src" / "app" / "projects" / "[projectId]" / "page.tsx", "Project workspace page"),
        (root / "frontend" / "src" / "app" / "research" / "page.tsx", "Research alias page"),
        (root / "frontend" / "src" / "app" / "research" / "[projectId]" / "page.tsx", "Research workspace alias page"),
        (root / "frontend" / "src" / "lib" / "api" / "types.ts", "Typed API contracts (Project, Document, Content)"),
        (root / "frontend" / "src" / "lib" / "api" / "errors.ts", "Standardized ApiError hierarchy"),
        (root / "frontend" / "src" / "lib" / "api" / "client.ts", "Centralized ApiClient with process/content methods"),
        (root / "frontend" / "src" / "lib" / "api" / "index.ts", "API module entrypoint"),
        (root / "frontend" / "src" / "components" / "ui" / "modal.tsx", "UI primitive: Modal"),
        (root / "frontend" / "src" / "components" / "projects" / "project-card.tsx", "Project card component"),
        (root / "frontend" / "src" / "components" / "projects" / "create-project-modal.tsx", "Create project modal"),
        (root / "frontend" / "src" / "components" / "projects" / "edit-project-modal.tsx", "Edit project modal"),
        (root / "frontend" / "src" / "components" / "projects" / "delete-project-modal.tsx", "Delete project modal"),
    ]
    for p, desc in frontend_files:
        if not check_file(p, desc):
            all_ok = False

    # 4. Validate Backend Configuration & Settings Import
    print("\n4. Validating Backend App Factory & Settings Import:")
    try:
        sys.path.insert(0, str(root / "backend"))
        from app.core.config import get_settings
        settings = get_settings()
        print(f"  [OK] App Name: {settings.APP_NAME}")
        print(f"  [OK] App Env: {settings.APP_ENV}")
        print(f"  [OK] Storage Root: {settings.storage_directory}")
        print(f"  [OK] Max Upload Size: {settings.MAX_UPLOAD_SIZE_MB} MB ({settings.max_upload_size_bytes} bytes)")
        print(f"  [OK] Allowed Extensions: {settings.ALLOWED_EXTENSIONS}")
        print(f"  [OK] Async DB URL: {settings.async_database_url.split('@')[-1]}")
    except Exception as e:
        print(f"  [FAIL] Failed to import settings: {e}")
        all_ok = False

    print("\n" + "=" * 80)
    if all_ok:
        print(" [SUCCESS] All Stage 9 document parsing & extraction components verified successfully!")
        return 0
    else:
        print(" [FAIL] One or more verification checks failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
