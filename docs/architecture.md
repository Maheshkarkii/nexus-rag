# AI Research Assistant — System Architecture & Design Document

> **Stage 8: Document Upload & File Ingestion Foundation**

---

## 1. Executive Overview

The **AI Research Assistant** is an enterprise-grade platform designed for multi-document research, semantic retrieval, cross-document comparison, tabular data analysis, and autonomous agentic synthesis.

Stage 8 introduces the **Document Upload & File Ingestion Subsystem**, establishing a clean architectural separation between:
1. **Relational Database Metadata (PostgreSQL)**: Filenames, MIME types, file sizes, processing states, and parent project associations.
2. **Binary File Storage (Local Storage Root / S3-ready)**: Project-isolated directory trees (`storage/projects/<project_id>/<stored_filename>`) with streaming writes, size bounds, and path traversal guards.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Client Browser / User                             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       │ HTTP Multipart / Next.js (Port 3000)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Frontend Application Layer                          │
│   - Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS             │
│   - Config Abstraction: NEXT_PUBLIC_API_URL (Default: http://localhost:8000)│
│   - Centralized ApiClient supporting multipart FormData & typed Document API│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       │ REST API (JSON & Multipart)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend Application                          │
│   - Python 3.13, Pydantic v2, Pydantic Settings, aiofiles, python-multipart │
│   - Configurable CORS Middleware & Exception Envelopes                      │
│   - Routes: /api/v1/projects and /api/v1/projects/{project_id}/documents    │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         StorageService                              │   │
│   │   - Streaming writes in 64 KB chunks                                │   │
│   │   - MAX_UPLOAD_SIZE_MB enforcement (Immediate partial-file cleanup) │   │
│   │   - Collision-resistant UUID filenames (e.g. 8f8e7e6d.pdf)          │   │
│   │   - Path traversal guards: is_relative_to(storage_root)             │   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
└──────────────────┬───────────────────┼───────────────────┬──────────────────┘
                   │                   │                   │
                   │ SQLAlchemy 2.x    │ Streaming Writes  │ REST/gRPC
                   │ (AsyncPG Pool)    │                   │ (6333/6334)
                   ▼                   ▼                   ▼
┌──────────────────────────┐ ┌───────────────────┐ ┌──────────────────────────┐
│ PostgreSQL 16 Database   │ │ Project Storage   │ │ Qdrant Vector DB         │
│ - `projects` table       │ │ storage/projects/ │ │ - High-performance index │
│ - `documents` table      │ │   <project_uuid>/ │ │ - Vector embeddings      │
│   (FK, UUID, Status)     │ │     <uuid>.<ext>  │ │   (Stage 10+)            │
└──────────────────────────┘ └───────────────────┘ └──────────────────────────┘
```

---

## 2. Ingestion & Storage Architecture

### 2.1 File Storage vs Database Metadata Separation

```text
User File Upload (e.g. "transformer_survey.pdf")
        │
        ▼
FastAPI Validation (Allowed Extensions, Content-Type, Size <= 50 MB)
        │
        ├──────────────────────────────────────────────────┐
        ▼                                                  ▼
Physical File System                                PostgreSQL Database
storage/projects/<project_id>/<uuid>.pdf             documents table:
  ├── Binary file chunks (64 KB stream)                ├── id (UUID v4)
  └── Isolated by project_id                           ├── project_id (FK -> projects.id)
                                                       ├── original_filename ("transformer_survey.pdf")
                                                       ├── stored_filename ("<uuid>.pdf")
                                                       ├── storage_path ("projects/<project_id>/<uuid>.pdf")
                                                       ├── mime_type ("application/pdf")
                                                       ├── file_extension (".pdf")
                                                       ├── file_size (bytes)
                                                       ├── status ("uploaded")
                                                       └── timestamps (created_at, updated_at)
```

### 2.2 Transactional Safety & Compensation

1. **Upload Failures**: If PostgreSQL throws an error after the physical file is written to disk, the transaction is rolled back and `StorageService.delete_file` immediately deletes the orphaned file.
2. **Deletion Flow**: Calling `DELETE /api/v1/projects/{project_id}/documents/{document_id}` removes the physical file from disk first, then deletes the relational database row. If the physical file is missing from disk (e.g. out-of-band cleanup), the operation logs a warning and successfully completes metadata deletion.

---

## 3. Database Schema

### `documents` Table
- `id`: `UUID` (Primary Key, Indexed)
- `project_id`: `UUID` (Foreign Key `projects.id` with `ON DELETE CASCADE`, Indexed)
- `original_filename`: `VARCHAR(255)` (Not Null)
- `stored_filename`: `VARCHAR(255)` (Not Null, Unique)
- `storage_path`: `VARCHAR(500)` (Not Null)
- `mime_type`: `VARCHAR(127)` (Not Null)
- `file_extension`: `VARCHAR(32)` (Not Null)
- `file_size`: `BIGINT` (Not Null)
- `status`: `VARCHAR(32)` (Not Null, Default `"uploaded"`, Indexed)
- `created_at`: `TIMESTAMP WITH TIME ZONE` (Not Null, Indexed)
- `updated_at`: `TIMESTAMP WITH TIME ZONE` (Not Null)

---

## 4. API Endpoints

| Method | Endpoint | Description | Status Code |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/projects/{project_id}/documents` | Multipart form upload of PDF, DOCX, TXT, CSV, XLSX, JSON | `201 Created` |
| `GET` | `/api/v1/projects/{project_id}/documents` | List all documents belonging to the project (ordered `created_at DESC`) | `200 OK` |
| `GET` | `/api/v1/projects/{project_id}/documents/{document_id}` | Fetch document metadata verifying project isolation | `200 OK` |
| `DELETE` | `/api/v1/projects/{project_id}/documents/{document_id}` | Permanently delete file from disk and database record | `204 No Content` |

---

## 5. Security & Ingestion Safeguards

1. **Path Traversal Guard**: All relative paths are sanitized and verified against the absolute root directory using `assert target.is_relative_to(storage_root)`. Any attempt to pass `../` or root paths raises a `BadRequestException`.
2. **Collision-Resistant Filenames**: Raw user filenames are never used on the filesystem; files are stored using server-generated UUIDs (`<uuid>.<extension>`).
3. **MIME & Extension Whitelisting**: Restricted to `.pdf`, `.docx`, `.txt`, `.csv`, `.xlsx`, `.xls`, `.json`.
4. **Streaming Size Bounds**: Uploads stream in 64 KB chunks. If total bytes exceed `MAX_UPLOAD_SIZE_MB` (default 50 MB), writing terminates immediately, the partial file is unlinked, and a `BadRequestException` is returned.
