# DocFlow System Architecture

## Overview

DocFlow is a production-grade asynchronous document processing system built with modern cloud-native
technologies. This document describes the architecture, design decisions, and operational procedures.

## Technology Stack

| Component        | Technology              | Purpose                          |
|-----------------|------------------------|----------------------------------|
| API             | FastAPI (Python 3.11)  | REST endpoints, SSE streaming    |
| Worker          | Celery 5.x             | Background task execution        |
| Message Broker  | Redis 7                | Celery broker + Pub/Sub events   |
| Database        | PostgreSQL 15          | Persistent storage               |
| Frontend        | Next.js 14 + TypeScript| User interface                   |

## Architecture Diagram

```
┌─────────────┐     HTTP      ┌──────────────┐     SQL      ┌─────────────┐
│   Browser   │◄─────────────►│  FastAPI App │◄────────────►│ PostgreSQL  │
│  (Next.js)  │               │              │              └─────────────┘
└─────────────┘               │  - Upload    │
       ▲                      │  - List      │     ENQUEUE  ┌─────────────┐
       │ SSE                  │  - Detail    │◄────────────►│    Redis    │
       │                      │  - Export    │              │ (Broker +   │
       └──────────────────────│  - Stream    │              │  Pub/Sub)   │
                              └──────────────┘              └─────────────┘
                                                                   ▲
                                                                   │ SUBSCRIBE
                                                            ┌──────┴──────┐
                                                            │   Celery    │
                                                            │   Worker    │
                                                            │             │
                                                            │ - Parse     │
                                                            │ - Extract   │
                                                            │ - Store     │
                                                            └─────────────┘
```

## Processing Pipeline

Each document flows through a deterministic multi-stage pipeline:

1. **document_received** — Worker acknowledges job, sets status to `processing`
2. **parsing_started** — File is opened and raw text is extracted
3. **parsing_completed** — Word count, character count captured
4. **extraction_started** — NLP/heuristic extraction begins
5. **extraction_completed** — Title, category, summary, keywords resolved
6. **final_result_stored** — Structured JSON persisted to PostgreSQL
7. **job_completed** — Status set to `completed`, SSE stream closes

## Resilience

- Celery tasks use `acks_late=True` — messages not acknowledged until task completes
- Failed jobs expose a `/retry` endpoint — idempotent re-queue up to `max_retries`
- Redis pub/sub channels are namespaced per job: `docflow:job:<uuid>`
- SSE streams heartbeat every 15 seconds and auto-close on terminal events
