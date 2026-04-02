"""
FastAPI routers — upload, list, detail, SSE progress, retry, edit, finalize, export.
"""

import json
import asyncio
import csv
import io
from typing import Optional
from uuid import UUID

import redis as _redis
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.core.redis_client import get_redis, get_pubsub_channel, get_job_status
from app.models.models import JobStatus
from app.schemas.schemas import (
    UploadResponse, PaginatedDocuments, DocumentListItem, JobDetailResponse,
    UpdateResultRequest, FinalizeRequest, ExportRequest, ExtractedResultResponse,
    JobSummary, DocumentResponse,
)
from app.services import document_service as svc

settings = get_settings()
router = APIRouter(prefix="/api/v1", tags=["docflow"])


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_documents(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload one or more documents and enqueue processing jobs."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    docs_out, jobs_out = [], []
    for file in files:
        doc, job = svc.create_document_and_job(db, file)
        docs_out.append(doc)
        jobs_out.append(job)

    queued_count = sum(1 for job in jobs_out if job.status == JobStatus.QUEUED)
    failed_count = len(jobs_out) - queued_count
    if failed_count:
        message = (
            f"{len(docs_out)} document(s) uploaded. "
            f"{queued_count} queued, {failed_count} failed to enqueue."
        )
    else:
        message = f"{len(docs_out)} document(s) uploaded and queued for processing."

    return UploadResponse(
        documents=[DocumentResponse.model_validate(d) for d in docs_out],
        jobs=[JobSummary.model_validate(j) for j in jobs_out],
        message=message,
    )


# ── List / Dashboard ──────────────────────────────────────────────────────────

@router.get("/documents", response_model=PaginatedDocuments)
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort_by: str = Query("uploaded_at"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """Paginated document list with search, filter, and sort."""
    items, total, total_pages = svc.list_documents(
        db, page, page_size, search, status, sort_by, sort_dir
    )
    return PaginatedDocuments(
        items=[DocumentListItem.model_validate(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── Job Detail ────────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: UUID, db: Session = Depends(get_db)):
    """Full job detail including document metadata, result, and event log."""
    job = svc.get_job_detail(db, str(job_id))
    return JobDetailResponse.model_validate(job)


# ── SSE Progress Stream ───────────────────────────────────────────────────────

@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: UUID):
    """
    Server-Sent Events endpoint.
    Subscribes to Redis Pub/Sub channel for the job and forwards events.
    Falls back to polling if already completed.
    """
    jid = str(job_id)

    async def event_generator():
        r = get_redis()

        # Send cached status immediately (if available)
        cached = get_job_status(jid)
        if cached:
            yield f"data: {json.dumps(cached)}\n\n"
            if cached.get("status") in ("completed", "failed", "finalized"):
                return

        # Subscribe to Pub/Sub channel
        pubsub = r.pubsub()
        channel = get_pubsub_channel(jid)
        pubsub.subscribe(channel)

        try:
            timeout = 0
            max_wait = 300  # 5 minutes max
            while timeout < max_wait:
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    payload = message["data"]
                    yield f"data: {payload}\n\n"
                    data = json.loads(payload)
                    if data.get("status") in ("completed", "failed"):
                        break
                else:
                    await asyncio.sleep(0.5)
                    timeout += 0.5
                    # Heartbeat every 15s
                    if int(timeout) % 15 == 0:
                        yield f": heartbeat\n\n"
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Retry ─────────────────────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/retry", response_model=JobSummary)
def retry_job(job_id: UUID, db: Session = Depends(get_db)):
    """Re-queue a failed job."""
    job = svc.retry_job(db, str(job_id))
    return JobSummary.model_validate(job)


# ── Edit Result ───────────────────────────────────────────────────────────────

@router.patch("/jobs/{job_id}/result", response_model=ExtractedResultResponse)
def update_result(
    job_id: UUID,
    payload: UpdateResultRequest,
    db: Session = Depends(get_db),
):
    """Edit extracted fields before finalization."""
    result = svc.update_result(db, str(job_id), payload)
    return ExtractedResultResponse.model_validate(result)


# ── Finalize ──────────────────────────────────────────────────────────────────

@router.post("/jobs/{job_id}/finalize", response_model=ExtractedResultResponse)
def finalize_result(
    job_id: UUID,
    payload: FinalizeRequest = FinalizeRequest(),
    db: Session = Depends(get_db),
):
    """Mark a result as finalized (locks further edits)."""
    result = svc.finalize_result(db, str(job_id), payload.reviewed_data)
    return ExtractedResultResponse.model_validate(result)


# ── Export ────────────────────────────────────────────────────────────────────

@router.post("/export")
def export_results(payload: ExportRequest, db: Session = Depends(get_db)):
    """Export one or more job results as JSON or CSV."""
    rows = svc.build_export_payload(db, [str(j) for j in payload.job_ids])

    if payload.format == "json":
        return JSONResponse(
            content=rows,
            headers={"Content-Disposition": "attachment; filename=docflow_export.json"},
        )

    # CSV export
    if not rows:
        raise HTTPException(status_code=404, detail="No exportable results found")

    output = io.StringIO()
    default_order = [
        "job_id",
        "document",
        "status",
        "finalized",
        "title",
        "category",
        "summary",
        "keywords",
        "word_count",
        "language",
        "finalized_at",
        "char_count",
    ]
    extra_keys = sorted({k for row in rows for k in row.keys() if k not in default_order})
    all_keys = default_order + extra_keys

    writer = csv.DictWriter(output, fieldnames=all_keys, extrasaction="ignore")
    writer.writeheader()

    def _clean_cell(value):
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, str):
            return value.replace("\x00", " ").replace("\r", " ").replace("\n", " ")
        return value

    for row in rows:
        flat = {k: _clean_cell(v) for k, v in row.items()}
        writer.writerow(flat)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=docflow_export.csv"},
    )


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok"}
