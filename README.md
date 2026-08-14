# AI Research Assistant

> **A modern, production-oriented platform for multi-document research, semantic retrieval, and autonomous agentic synthesis.**

---

## 1. Description

The **AI Research Assistant** is a full-stack, portfolio-grade system designed to empower researchers and knowledge workers to ingest diverse documents (PDFs, DOCX, Markdown, CSV, XLSX, JSON), index semantic knowledge, perform grounded retrieval-augmented generation (RAG) with precise citations, compare complex studies, and execute autonomous multi-step research tasks with LangGraph.

---

## 2. Current Status

> [!NOTE]
> **Current Phase: Stage 56 — Advanced Research Agent & Multi-Agent System Complete.**
>
> The production RAG platform features strongly typed multi-agent research orchestration, strict tool authorization, and verification gates:
>
> - **Multi-Agent Research Orchestrator** ([`agentic_research.py`](file:///C:/Users/Mahesh%20Karki/Downloads/Mahesh/AI%20Research%20Assistant/backend/app/services/agentic_research.py)): Strongly typed state (`ResearchState`), task decomposition (`ResearchPlan`), specialized planner/verifier/synthesis agents, and strict tool authorization (`ToolRegistry`).
> - **Claim Verification & Provenance**: Evidence normalization across text, tables, figures, and graph relationships with claim-evidence mapping and hallucination prevention.
> - **Comprehensive Test Suite & Evaluation**: 189 backend unit & integration tests passing with 0 failures (`pytest -v`), 100% evaluation pass rate (`run_eval.py`).

---

## 3. Technology Stack

- **Frontend**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Lucide Icons
- **Frontend API Client**: Centralized `ApiClient` with typed responses, custom `ApiError` hierarchy, `FormData` multipart uploads, `processDocument`, `getDocumentContent`, and `AbortController` timeouts
- **Backend**: FastAPI, Python 3.13, Uvicorn, Pydantic v2, Pydantic Settings, `aiofiles`, `python-multipart`
- **Document Extractors**: `pypdf` (PDF), `python-docx` (DOCX), `openpyxl` (Excel), standard library `csv` & `json`
- **File Storage**: Local Project-Isolated Storage (`storage/projects/<project_id>/`) with Docker volume persistence
- **Relational Database**: PostgreSQL 16 (persistent Docker volume)
- **ORM & Migrations**: SQLAlchemy 2.0 (AsyncPG), Alembic
- **Vector Database**: Qdrant 1.13+ (persistent Docker volume)
- **Infrastructure & Tooling**: Docker, Docker Compose, Pytest, ESLint

---

## 4. Architecture

### Inter-Service Communication & Parsing Pipeline

```
Browser (User) 
   │
   ├─► Frontend (Next.js :3000) ──► Centralized ApiClient
   │     ├── /projects (List & Create Workspaces)
   │     └── /projects/[projectId] (Workspace Shell)
   │                                   │
   │                                   │ HTTP REST (NEXT_PUBLIC_API_URL)
   │                                   ▼
   └─► FastAPI Backend (:8000) ◄───────┘
          │
          ├──► Master Router (/api/v1)
          │       ├── /health (Liveness & Readiness Probes)
          │       ├── /projects (Workspace Management CRUD)
          │       └── /projects/{project_id}/documents (Upload, List, Get, Delete)
          │             ├── POST /{document_id}/process (Trigger Text Extraction)
          │             └── GET /{document_id}/content (Inspect Extracted Text)
          │
          ├──► DocumentProcessingService
          │       ├── Format Detection & Processor Registry
          │       │     ├── PDFProcessor (pypdf page iteration)
          │       │     ├── DocxProcessor (python-docx paragraphs & tables)
          │       │     ├── TextProcessor (multi-encoding fallback)
          │       │     ├── CSVProcessor (tabular row & column formatter)
          │       │     ├── ExcelProcessor (openpyxl multi-sheet workbook)
          │       │     └── JSONProcessor (hierarchical recursive formatter)
          │       │
          │       ├── Text Normalization (CRLF, control chars, whitespace)
          │       └── Atomic Status Transitions (uploaded -> processing -> ready / failed)
          │
          ├──► StorageService (Local Disk `storage/projects/<project_id>/<stored_filename>`)
          │
          └──► SQLAlchemy 2.x Async Engine (PostgreSQL 16 `documents` table with extracted_text)
```

---

## 5. Local Development & Getting Started

### Prerequisites

- [Docker & Docker Compose](https://docs.docker.com/get-docker/) (v20+ / Compose v2+)
- *Optional for native development*: Python 3.11+ / `uv` and Node.js 20+ / `npm`

---

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd "AI Research Assistant"
```

---

### Step 2: Configure Environment Variables

Copy the template `.env.example` to create your local `.env` configuration:

```bash
# On Linux / macOS / Git Bash:
cp .env.example .env

# On Windows PowerShell:
Copy-Item .env.example .env
```

---

### Step 3: Start the Development Environment with Docker Compose

Build and launch all 4 services (Frontend, Backend, PostgreSQL, Qdrant):

```bash
docker compose up --build
```

---

### Step 4: Access Services & Documentation

Once the containers are running, access the services using your browser:

| Service | URL | Description |
| :--- | :--- | :--- |
| **Frontend Application** | [http://localhost:3000](http://localhost:3000) | Next.js Landing & Dashboard with Live API Probe |
| **Research Projects** | [http://localhost:3000/projects](http://localhost:3000/projects) | Project workspace listing, creation, and management |
| **Backend API Root** | [http://localhost:8000/](http://localhost:8000/) | Service discovery & status |
| **Liveness Health Check** | [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) | `{"status": "healthy"}` |
| **Readiness Probe** | [http://localhost:8000/api/v1/health/ready](http://localhost:8000/api/v1/health/ready) | Evaluates live PostgreSQL connection |
| **Projects API** | [http://localhost:8000/api/v1/projects](http://localhost:8000/api/v1/projects) | Project workspace CRUD endpoints |
| **Documents API** | [http://localhost:8000/api/v1/projects/{project_id}/documents](http://localhost:8000/api/v1/projects/{project_id}/documents) | Document upload, listing, and deletion |
| **Process Document** | [http://localhost:8000/api/v1/projects/{project_id}/documents/{document_id}/process](http://localhost:8000/api/v1/projects/{project_id}/documents/{document_id}/process) | Trigger format-specific text extraction |
| **Document Content** | [http://localhost:8000/api/v1/projects/{project_id}/documents/{document_id}/content](http://localhost:8000/api/v1/projects/{project_id}/documents/{document_id}/content) | Inspect normalized text & statistics |
| **Swagger OpenAPI Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive API documentation |
| **Qdrant REST API** | [http://localhost:6333/dashboard](http://localhost:6333/dashboard) | Vector database dashboard |

---

### Step 5: Running Tests & Build Validation

```bash
# 1. Run all backend tests (health, CORS, database session, project CRUD, documents, parsing)
uv run --directory backend pytest -v

# 2. Run frontend build and type checks
npm run build --prefix frontend

# 3. Run frontend lint
npm run lint --prefix frontend

# 4. Run full Stage 9 environment verification
uv run python scripts/verify-env.py
```

---

## 6. Project Monorepo Structure

```
ai-research-assistant/
├── backend/
│   ├── alembic/
│   │   ├── versions/
│   │   │   ├── 0001_initial_projects_table.py # Initial projects table migration
│   │   │   ├── 0002_create_documents_table.py # Document metadata table & indexes
│   │   │   └── 0003_add_document_extracted_content.py # Extracted text & stats
│   │   ├── env.py                             # Async Alembic migration runner
│   │   └── script.py.mako                     # Migration file template
│   ├── alembic.ini                            # Alembic CLI configuration
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── health.py                  # Liveness & live PostgreSQL readiness probes
│   │   │   │   ├── projects.py                # Research project CRUD endpoints
│   │   │   │   └── documents.py               # Document upload, list, process, content, delete
│   │   │   └── router.py                      # Master API router (/api/v1)
│   │   ├── core/
│   │   │   ├── config.py                      # Settings (STORAGE_PATH, MAX_UPLOAD_SIZE_MB)
│   │   │   ├── logging.py                     # Structured development logger
│   │   │   └── exceptions.py                  # AppException hierarchy & error handlers
│   │   ├── db/
│   │   │   ├── models/
│   │   │   │   ├── project.py                 # Project workspace model with documents relation
│   │   │   │   └── document.py                # Document model with extracted_text columns
│   │   │   ├── base.py                        # Declarative Base, UUID, & Timestamp mixins
│   │   │   └── session.py                     # Async engine & get_db session dependency
│   │   ├── dependencies/
│   │   │   └── common.py                      # FastAPI dependency injection helpers
│   │   ├── schemas/
│   │   │   ├── common.py                      # Standardized response & error models
│   │   │   ├── project.py                     # ProjectCreate, ProjectUpdate, ProjectResponse
│   │   │   └── document.py                    # DocumentResponse & DocumentContentResponse
│   │   ├── services/
│   │   │   ├── storage.py                     # StorageService abstraction with path safety
│   │   │   ├── project.py                     # Asynchronous project database service
│   │   │   ├── document.py                    # Ingestion pipeline & transactional compensation
│   │   │   └── document_processing/           # Stage 9 Extraction Subsystem
│   │   │       ├── base.py                    # ExtractionResult & BaseDocumentProcessor
│   │   │       ├── normalizer.py              # Text normalizer utility
│   │   │       ├── pdf_processor.py           # PDFProcessor (pypdf page extractor)
│   │   │       ├── docx_processor.py          # DocxProcessor (python-docx headings & tables)
│   │   │       ├── text_processor.py          # TextProcessor (multi-encoding fallback)
│   │   │       ├── csv_processor.py           # CSVProcessor (tabular formatting)
│   │   │       ├── excel_processor.py         # ExcelProcessor (openpyxl multi-sheet)
│   │   │       ├── json_processor.py          # JSONProcessor (hierarchical formatter)
│   │   │       ├── registry.py                # Processor registry by extension/MIME
│   │   │       └── service.py                 # DocumentProcessingService coordinator
│   │   └── main.py                            # FastAPI application factory & CORS setup
│   ├── tests/
│   │   ├── api/
│   │   │   ├── test_health.py                 # Health, readiness, and CORS header tests
│   │   │   ├── test_projects.py               # Complete project CRUD API test suite
│   │   │   ├── test_documents.py              # Document upload & lifecycle test suite
│   │   │   └── test_document_processing.py    # Document processing & content test suite
│   │   ├── services/
│   │   │   ├── test_storage.py                # Storage service unit test suite
│   │   │   └── test_processors.py             # Format processors unit test suite
│   │   ├── core/
│   │   │   ├── test_config.py                 # Config, CORS parsing, and DB URL tests
│   │   │   └── test_exceptions.py             # Custom exception handler tests
│   │   ├── db/
│   │   │   └── test_session.py                # Session lifecycle & connectivity tests
│   │   ├── models/
│   │   │   └── test_project.py                # Project CRUD, UUID, & timestamp tests
│   │   └── conftest.py                        # In-memory test DB & isolated temp storage
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx                     # Root layout & dark theme shell
│   │   │   ├── page.tsx                       # Dashboard & Live API status integration
│   │   │   ├── projects/
│   │   │   │   ├── page.tsx                   # Research Projects listing & search
│   │   │   │   └── [projectId]/
│   │   │   │       └── page.tsx               # Project Workspace shell & capabilities
│   │   │   ├── research/
│   │   │   │   ├── page.tsx                   # Research listing route alias
│   │   │   │   └── [projectId]/
│   │   │   │       └── page.tsx               # Research workspace alias
│   │   │   ├── loading.tsx                    # Next.js route loading skeleton
│   │   │   ├── error.tsx                      # Route error boundary
│   │   │   ├── not-found.tsx                  # 404 screen
│   │   │   └── globals.css                    # Tailwind tokens, HSL variables, glass styles
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── app-shell.tsx              # Top-level responsive application shell
│   │   │   │   ├── sidebar.tsx                # Collapsible navigation sidebar
│   │   │   │   └── header.tsx                 # Contextual header with search placeholder
│   │   │   ├── projects/
│   │   │   │   ├── project-card.tsx           # Project card with metadata & actions
│   │   │   │   ├── create-project-modal.tsx   # Accessible project creation modal
│   │   │   │   ├── edit-project-modal.tsx     # Project editing modal
│   │   │   │   └── delete-project-modal.tsx   # Destructive deletion confirmation modal
│   │   │   └── ui/
│   │   │       ├── api-status-card.tsx        # Live FastAPI backend communication card
│   │   │       ├── modal.tsx                  # Accessible dialog primitive
│   │   │       ├── button.tsx                 # Button primitive
│   │   │       ├── card.tsx                   # Card primitive
│   │   │       ├── badge.tsx                  # Badge primitive
│   │   │       ├── separator.tsx              # Separator primitive
│   │   │       ├── input.tsx                  # Input primitive
│   │   │       ├── container.tsx              # Layout container
│   │   │       └── empty-state.tsx            # Empty state component
│   │   └── lib/
│   │       ├── api/
│   │       │   ├── client.ts                  # Centralized ApiClient with process/content methods
│   │       │   ├── errors.ts                  # Standardized ApiError hierarchy
│   │       │   ├── types.ts                   # Typed API contracts (Project, Document, Content)
│   │       │   └── index.ts                   # API module entrypoint
│   │       ├── api.ts                         # Backward-compatible API re-export
│   │       ├── config.ts                      # Centralized NEXT_PUBLIC_API_URL abstraction
│   │       └── utils.ts                       # Class name merger
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   └── tailwind.config.ts
│
├── docs/
│   └── architecture.md                        # Comprehensive system architecture & data flow
│
├── scripts/
│   └── verify-env.py                          # Stage verification diagnostic script
│
├── .env.example                               # Environment template with placeholders
├── docker-compose.yml                         # Orchestration for all 4 services + storage volume
├── README.md                                  # Project documentation
└── LICENSE                                    # MIT License
```

---

## 7. Development Roadmap

Future stages will incrementally deliver production-grade AI capabilities:

- **Stage 10**: Intelligent Chunking & Document Structure (Recursive semantic chunking, page/section header tagging)
- **Stage 11**: Vector Embeddings & Hybrid Search (SentenceTransformers, Qdrant dense/sparse collections)
- **Stage 12**: Grounded RAG & Citations (Multi-LLM provider abstraction, re-ranking, source citations)
- **Stage 13**: Multi-Document Comparison & Dataset Analytics (Cross-paper diffing, structured table querying)
- **Stage 14**: Autonomous Research Agents with LangGraph (Multi-step research loops, plan-and-solve execution)

---

## 8. License

Distributed under the MIT License. See [`LICENSE`](file:///C:/Users/Mahesh%20Karki/Downloads/Mahesh/AI%20Research%20Assistant/LICENSE) for more information.
