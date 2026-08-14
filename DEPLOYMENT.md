# AI Research Assistant — Production Deployment Guide

## 1. Overview & Architecture

The **AI Research Assistant** is built as a containerized, production-ready RAG platform.

```text
                    ┌───────────────┐
                    │    Client     │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ Next.js UI    │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ FastAPI API   │
                    └───────┬───────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
     PostgreSQL         Qdrant Vector      Async Worker
     Database             Engine             Pool
          │                 │                 │
          └─────────────────┼─────────────────┘
                            ▼
                     Persistent Storage
```

---

## 2. Environment Configuration

Copy `.env.example` to `.env` in the root project directory:

```bash
cp .env.example .env
```

### Key Environment Variables
* `APP_ENV`: `production` or `development`.
* `DEBUG`: Set to `false` in production.
* `DATABASE_URL`: `postgresql+asyncpg://postgres:password@postgres:5432/ai_research_db`
* `QDRANT_URL`: `http://qdrant:6333`
* `LLM_API_KEY`: API key for Gemini / OpenRouter / OpenAI.
* `MAX_CONCURRENT_JOBS`: `5` (Background job concurrency limit).
* `EMBEDDING_BATCH_SIZE`: `32` (Vector inference batch size).

---

## 3. Docker Deployment Commands

### Build & Launch Containers
```bash
docker compose build
docker compose up -d
```

### Check Container Status & Health
```bash
docker compose ps
```

### View Logs
```bash
docker compose logs -f backend
```

---

## 4. Persistent Storage Volumes

Data persistence is managed via named Docker volumes:
* `ai_research_postgres_data`: PostgreSQL relational database tables.
* `ai_research_qdrant_data`: Qdrant vector embeddings and collection indexes.
* `ai_research_storage_data`: Uploaded documents, extracted text chunks, and generated research reports.

---

## 5. Health & Readiness Monitoring

* **System Health Endpoint**: `GET /api/v1/health`
* **Observability & Metrics Endpoint**: `GET /api/v1/observability/metrics`

---

## 6. Backup & Recovery

### PostgreSQL Backup
```bash
docker exec -t ai-research-postgres pg_dump -U postgres ai_research_db > backup_$(date +%Y%m%d).sql
```

### PostgreSQL Restore
```bash
cat backup.sql | docker exec -i ai-research-postgres psql -U postgres ai_research_db
```
