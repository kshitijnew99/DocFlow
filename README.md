# DocFlow — Async Document Processing System

A production-style full-stack application for uploading, processing, reviewing, and exporting documents
asynchronously. Built with **FastAPI**, **Celery**, **Redis**, **PostgreSQL**, and **Next.js + TypeScript**.

---

## Demo

> Short demo video: _[Record and insert link here]_

Sample test files are in `samples/test_files/`.  
Sample export outputs are in `samples/exported_outputs/`.

Render deployment guide: `DEPLOY_RENDER.md`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Browser (Next.js)                          │
│  Upload Page │ Dashboard │ Job Detail (SSE live progress + editor)  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP / SSE
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                              │
│  POST /upload  GET /documents  GET /jobs/:id  GET /jobs/:id/stream  │
│  POST /jobs/:id/retry  PATCH /jobs/:id/result  POST /export        │
└──────────┬──────────────────────────────────────┬───────────────────┘
           │ SQL (SQLAlchemy)                      │ Pub/Sub subscribe
           ▼                                      ▼
┌──────────────────┐                   ┌──────────────────────────────┐
│   PostgreSQL 15  │                   │          Redis 7             │
│                  │                   │  - Celery broker (DB 1)      │
│  documents       │                   │  - Celery results (DB 2)     │
│  processing_jobs │                   │  - Pub/Sub events (DB 0)     │
│  extracted_results│                  │  - Status cache  (DB 0)      │
│  job_events      │                   └──────────┬───────────────────┘
└──────────────────┘                              │ Publish events
                                                  ▼
                                    ┌─────────────────────────────┐
                                    │       Celery Worker         │
                                    │                             │
                                    │  process_document task      │
                                    │  ┌─────────────────────┐   │
                                    │  │ 1. document_received │   │
                                    │  │ 2. parsing_started   │   │
                                    │  │ 3. parsing_completed │   │
                                    │  │ 4. extraction_started│   │
                                    │  │ 5. extraction_done   │   │
                                    │  │ 6. result_stored     │   │
                                    │  │ 7. job_completed     │   │
                                    │  └─────────────────────┘   │
                                    └─────────────────────────────┘
```

### Key Design Decisions

| Concern | Choice | Rationale |
|---|---|---|
| Progress delivery | Server-Sent Events (SSE) | Simpler than WebSockets; unidirectional fits the use case |
| Pub/Sub | Redis channels per job | Namespaced isolation; zero fanout overhead per job |
| Status cache | Redis `SETEX` alongside Pub/Sub | SSE clients joining late get instant current state |
| Task reliability | `acks_late=True`, `prefetch=1` | Task not ACK'd until complete; prevents loss on crash |
| DB sessions in workers | Fresh `SessionLocal()` per task | Workers are separate processes; no shared ORM state |
| Retries | Manual endpoint + DB counter | Max-retries enforced; idempotent re-queue with new task ID |

---

## Project Structure

```
docflow/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py          # All API endpoints
│   │   ├── core/
│   │   │   ├── config.py          # Pydantic settings
│   │   │   ├── database.py        # SQLAlchemy engine + session
│   │   │   └── redis_client.py    # Pub/Sub publish + status cache
│   │   ├── models/
│   │   │   └── models.py          # SQLAlchemy ORM models
│   │   ├── schemas/
│   │   │   └── schemas.py         # Pydantic request/response DTOs
│   │   ├── services/
│   │   │   └── document_service.py # Business logic layer
│   │   ├── workers/
│   │   │   ├── celery_app.py      # Celery configuration
│   │   │   └── tasks.py           # process_document task + pipeline
│   │   └── main.py                # FastAPI app + CORS + lifespan
│   ├── alembic/                   # DB migrations
│   ├── tests/
│   │   ├── test_api.py            # Integration tests (TestClient)
│   │   └── test_tasks.py          # Unit tests for processing logic
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic.ini
│
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── Layout.tsx          # Nav + shell
│       │   ├── DropZone.tsx        # react-dropzone upload UI
│       │   ├── JobCard.tsx         # Dashboard list item
│       │   ├── StatusBadge.tsx     # Coloured status pill
│       │   ├── ProgressBar.tsx     # Animated progress bar
│       │   ├── LiveProgress.tsx    # SSE event consumer + live feed
│       │   └── ResultEditor.tsx    # Edit + finalize extracted result
│       ├── hooks/
│       │   └── useJobStream.ts     # EventSource hook for SSE
│       ├── pages/
│       │   ├── index.tsx           # Dashboard (search/filter/sort/export)
│       │   ├── upload.tsx          # Upload + live progress after upload
│       │   └── jobs/[id].tsx       # Job detail + result editor
│       ├── services/
│       │   └── api.ts              # Axios API client
│       ├── types/
│       │   └── index.ts            # TypeScript interfaces
│       └── utils/
│           └── index.ts            # Formatters, constants
│
├── samples/
│   ├── test_files/                 # Sample documents to upload
│   └── exported_outputs/           # Sample JSON/CSV exports
│
└── docker-compose.yml
```

---

## Setup & Run Instructions

### Prerequisites

- [Docker](https://www.docker.com/) + Docker Compose v2
- OR: Python 3.11+, Node.js 20+, PostgreSQL 15, Redis 7

---

### Option A — Docker Compose (Recommended)

```bash
# 1. Clone the repo
git clone <repo-url>
cd docflow

# 2. Create local environment file (never commit real secrets)
cp .env.example .env

# 3. Start all services (Postgres, Redis, FastAPI backend, Celery worker, Next.js frontend)
docker compose up --build

# 4. Open the app
open http://localhost:3000      # Frontend
open http://localhost:8000/docs # Backend Swagger UI
```

On first start Docker Compose will:
- Spin up PostgreSQL and Redis
- Run database table creation via SQLAlchemy `create_all` on FastAPI startup
- Start the Celery worker connected to the same Redis broker
- Start the Next.js dev server

---

### Option B — Local Development (without Docker)

#### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (copy and edit local values)
cp .env.example .env
# Edit DATABASE_URL, REDIS_URL, etc. in .env

# Run database migrations
alembic upgrade head

# Start FastAPI
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# In a separate terminal — start Celery worker
celery -A app.workers.celery_app worker --loglevel=info --concurrency=4
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Set API URL
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
# Note: this project is Next.js, so use NEXT_PUBLIC_API_URL (not VITE_API_BASE_URL)

# Start dev server
npm run dev
# Open http://localhost:3000
```

---

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `set in .env` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for status cache + Pub/Sub |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery message broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | Celery result storage |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend API base URL for Next.js |
| `UPLOAD_DIR` | `./uploads` | Where uploaded files are stored on disk |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum individual file size |
| `SECRET_KEY` | `set in .env` | App secret (required outside local test runs) |

---

## Running Tests

```bash
cd backend

# Install test dependencies (included in requirements.txt)
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --tb=short
```

Tests use SQLite in-memory and mock Celery — no running infrastructure required.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/upload` | Upload one or more files (multipart/form-data) |
| `GET` | `/api/v1/documents` | List documents (search, filter, sort, paginate) |
| `GET` | `/api/v1/jobs/{job_id}` | Full job detail (document, result, event log) |
| `GET` | `/api/v1/jobs/{job_id}/stream` | SSE stream of live progress events |
| `POST` | `/api/v1/jobs/{job_id}/retry` | Re-queue a failed job |
| `PATCH` | `/api/v1/jobs/{job_id}/result` | Edit extracted fields |
| `POST` | `/api/v1/jobs/{job_id}/finalize` | Lock result as finalized |
| `POST` | `/api/v1/export` | Export selected jobs as JSON or CSV |
| `GET` | `/api/v1/health` | Health check |

Interactive docs at `http://localhost:8000/docs`

---

## Supported File Types

| Extension | MIME Type | Notes |
|---|---|---|
| `.txt` | text/plain | Full text parsing |
| `.md` | text/markdown | Markdown parsed as text |
| `.csv` | text/csv | Header + data rows |
| `.json` | application/json | Structured data extraction |
| `.xml` | application/xml | Config / markup |
| `.pdf` | application/pdf | Text extraction (binary fallback) |

---

## Workflow

```
Upload → [QUEUED] → Celery picks up → [PROCESSING]
  ↓
  Stage 1: document_received     (5%)
  Stage 2: parsing_started       (20%)
  Stage 3: parsing_completed     (45%)
  Stage 4: extraction_started    (55%)
  Stage 5: extraction_completed  (75%)
  Stage 6: final_result_stored   (90%)
  Stage 7: job_completed         (100%)
  ↓
[COMPLETED] → Review in UI → Edit fields → [FINALIZED] → Export JSON/CSV
                                ↓
                        (if error) [FAILED] → Retry (max 3)
```

---

## Assumptions

1. **Processing logic is simulated** — The business logic (parsing, extraction) uses heuristics rather
   than OCR or real NLP. The system architecture (async pipeline, Pub/Sub, SSE) is fully real.

2. **File storage is local disk** — Files are stored on the server filesystem. A production deployment
   would swap this for S3 or GCS via an abstraction layer (see Tradeoffs).

3. **No authentication** — Auth was excluded to keep the scope focused on async architecture. The bonus
   point implementation would add JWT-based auth via `python-jose`.

4. **Single worker process** — The Docker Compose setup runs one Celery worker with 4 threads of
   concurrency. Scale by adding more worker containers or increasing `--concurrency`.

5. **SSE over WebSockets** — SSE was chosen for simplicity. It is unidirectional (server → client) and
   sufficient for progress streaming. WebSockets would be needed for bidirectional real-time features.

---

## Tradeoffs

| Decision | Tradeoff Made | Alternative |
|---|---|---|
| SSE for progress | Simpler; HTTP/1.1 compatible | WebSockets for bidirectional |
| Local file storage | Zero infra overhead in dev | S3/GCS for production scale |
| Heuristic NLP | Always works, no API keys | Integrate OpenAI/spaCy for real extraction |
| SQLite in tests | Fast, zero setup | TestContainers with real PostgreSQL |
| `create_all` on startup | Convenient for dev | Alembic migrations only in production |
| Single Celery queue | Simpler routing | Priority queues for large vs small files |

---

## Limitations

1. **PDF text extraction** — PDFs without embedded text (scanned images) are not OCR'd. They fall back
   to a "binary file" placeholder. Real PDF support would require `pdfminer` or `pymupdf`.

2. **No cancellation** — Once a Celery task starts, it cannot be cancelled via the API. Celery's
   `revoke()` could be added as a `DELETE /jobs/{id}` endpoint.

3. **No large-file chunking** — Files are read entirely into memory. Files >100 MB should be streamed
   and processed in chunks.

4. **Redis Pub/Sub is fire-and-forget** — If the SSE client is not connected when an event fires,
   the event is lost. The Redis status cache (`SETEX`) mitigates this by providing the latest state
   on reconnect.

5. **No authentication or multi-tenancy** — All documents are visible to all users. Row-level security
   and user sessions would be required for production.

---

## AI Tools Used

- **Claude (Anthropic)** was used to assist in scaffolding boilerplate, reviewing architectural
  decisions, and generating documentation. All code was reviewed, understood, and validated by the
  author. The system design, architecture decisions, and implementation strategy are original.

---

## Bonus Features Implemented

- [x] Docker Compose full-stack setup
- [x] Comprehensive test suite (integration + unit, 25+ test cases)
- [x] Idempotent retry handling with `max_retries` guard and new task ID per retry
- [x] File storage abstraction (save function isolated in service layer — swap to S3 by editing one function)
- [x] Clean deployment-ready structure with separate API / service / worker / schema layers
- [x] Thoughtful edge case handling: file type validation, size limits, late SSE join via status cache,
      finalized result locking, export of non-existent job IDs
