"""
Service layer — business logic between API routes and DB/workers.
"""

import os
import uuid
import shutil
from datetime import datetime
from typing import Optional
from pathlib import Path

from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException, status

from app.core.config import get_settings
from app.models.models import Document, ProcessingJob, ExtractedResult, JobStatus
from app.schemas.schemas import UpdateResultRequest

settings = get_settings()


def _save_upload(file: UploadFile) -> tuple[str, str, int, str]:
    """Persist uploaded file to disk. Returns (path, stored_filename, size, ext)."""
    ext = Path(file.filename or "file").suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{ext}' is not allowed. "
                   f"Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    unique_name = f"{uuid.uuid4()}{ext}"
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / unique_name

    content = file.file.read()
    size = len(content)
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    with open(dest, "wb") as f:
        f.write(content)

    return str(dest), unique_name, size, ext


def create_document_and_job(db: Session, file: UploadFile) -> tuple[Document, ProcessingJob]:
    """Upload a file, persist metadata, enqueue Celery task."""
    from app.workers.tasks import process_document

    file_path, stored_name, size, ext = _save_upload(file)
    mime = file.content_type or "application/octet-stream"

    doc = Document(
        filename=stored_name,
        original_filename=file.filename or stored_name,
        file_path=file_path,
        file_size=size,
        file_type=ext,
        mime_type=mime,
    )
    db.add(doc)
    db.flush()  # get doc.id without commit

    job = ProcessingJob(
        document_id=doc.id,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.add(job)
    db.commit()
    db.refresh(doc)
    db.refresh(job)

    # Dispatch to Celery — fire and forget
    task = process_document.apply_async(
        args=[str(job.id), str(doc.id), file_path, doc.original_filename, ext],
        task_id=str(uuid.uuid4()),
    )
    job.celery_task_id = task.id
    db.commit()

    return doc, job


def list_documents(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    sort_by: str = "uploaded_at",
    sort_dir: str = "desc",
):
    """Paginated, searchable, filterable document list."""
    query = db.query(Document)

    if search:
        query = query.filter(
            Document.original_filename.ilike(f"%{search}%")
        )

    if status_filter:
        query = (
            query
            .join(ProcessingJob, Document.id == ProcessingJob.document_id)
            .filter(ProcessingJob.status == status_filter)
        )

    col_map = {
        "uploaded_at": Document.uploaded_at,
        "filename": Document.original_filename,
        "file_size": Document.file_size,
    }
    sort_col = col_map.get(sort_by, Document.uploaded_at)
    if sort_dir == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = (total + page_size - 1) // page_size

    return items, total, total_pages


def get_job_detail(db: Session, job_id: str) -> ProcessingJob:
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.id == job_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def retry_job(db: Session, job_id: str) -> ProcessingJob:
    """Re-queue a failed job."""
    from app.workers.tasks import process_document
    from app.core.redis_client import publish_event

    job = get_job_detail(db, job_id)
    if job.status not in (JobStatus.FAILED,):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only failed jobs can be retried. Current status: {job.status}",
        )
    if job.retry_count >= job.max_retries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Max retries ({job.max_retries}) exhausted",
        )

    doc = job.document
    job.status = JobStatus.QUEUED
    job.progress = 0.0
    job.current_stage = None
    job.error_message = None
    job.retry_count += 1
    job.completed_at = None
    db.commit()

    task = process_document.apply_async(
        args=[str(job.id), str(doc.id), doc.file_path,
              doc.original_filename, doc.file_type],
        task_id=str(uuid.uuid4()),
    )
    job.celery_task_id = task.id
    db.commit()
    db.refresh(job)

    publish_event(str(job.id), {
        "job_id": str(job.id),
        "event_type": "job_queued",
        "stage": "queued",
        "progress": 0.0,
        "message": f"Retry #{job.retry_count} queued",
        "status": "queued",
        "timestamp": datetime.utcnow().isoformat(),
    })

    return job


def update_result(db: Session, job_id: str, payload: UpdateResultRequest) -> ExtractedResult:
    job = get_job_detail(db, job_id)
    result = job.result
    if not result:
        raise HTTPException(status_code=404, detail="No result found for this job")
    if result.is_finalized:
        raise HTTPException(status_code=400, detail="Finalized results cannot be edited")

    for field, val in payload.model_dump(exclude_none=True).items():
        if hasattr(result, field):
            setattr(result, field, val)
    result.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(result)
    return result


def finalize_result(db: Session, job_id: str, reviewed_data: Optional[dict] = None) -> ExtractedResult:
    job = get_job_detail(db, job_id)
    result = job.result
    if not result:
        raise HTTPException(status_code=404, detail="No result to finalize")
    if result.is_finalized:
        raise HTTPException(status_code=400, detail="Already finalized")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job must be completed before finalizing")

    if reviewed_data:
        result.reviewed_data = reviewed_data
    result.is_finalized = True
    result.finalized_at = datetime.utcnow()
    job.status = JobStatus.FINALIZED
    db.commit()
    db.refresh(result)
    return result


def build_export_payload(db: Session, job_ids: list[str]) -> list[dict]:
    """Collect finalized results for export."""
    def _looks_binaryish(text: str) -> bool:
        if not text:
            return False
        sample = text[:1200]
        if sample.startswith("%PDF-"):
            return True
        replacement_count = sample.count("\ufffd")
        if replacement_count >= 4:
            return True
        printable_ratio = sum(1 for ch in sample if ch.isprintable()) / max(len(sample), 1)
        return printable_ratio < 0.78

    def _clean_text(value: Optional[str], max_len: Optional[int] = None) -> Optional[str]:
        if value is None:
            return None
        if _looks_binaryish(value):
            return "[Binary content omitted]"
        cleaned = value.replace("\x00", " ").replace("\r", " ").replace("\n", " ")
        cleaned = " ".join(cleaned.split())
        if max_len and len(cleaned) > max_len:
            return cleaned[:max_len].rstrip() + "..."
        return cleaned

    def _clean_keywords(value) -> list[str]:
        if isinstance(value, list):
            return [str(v) for v in value if v is not None]
        if value is None:
            return []
        return [str(value)]

    rows = []
    for jid in job_ids:
        try:
            job = get_job_detail(db, jid)
        except HTTPException:
            continue
        result = job.result
        if not result:
            continue
        doc = job.document

        reviewed = result.reviewed_data if isinstance(result.reviewed_data, dict) else {}

        title = reviewed.get("title") or result.title
        category = reviewed.get("category") or result.category
        summary = reviewed.get("summary") or result.summary
        keywords = reviewed.get("keywords") if "keywords" in reviewed else result.keywords

        word_count = reviewed.get("word_count") if "word_count" in reviewed else result.word_count
        char_count = reviewed.get("char_count") if "char_count" in reviewed else result.char_count
        language = reviewed.get("language") if "language" in reviewed else result.language

        rows.append({
            "job_id": str(job.id),
            "document": doc.original_filename if doc else None,
            "status": job.status.value,
            "finalized": result.is_finalized,
            "title": _clean_text(str(title) if title is not None else None, max_len=500),
            "category": _clean_text(str(category) if category is not None else None, max_len=200),
            "summary": _clean_text(str(summary) if summary is not None else None, max_len=1000),
            "keywords": _clean_keywords(keywords),
            "word_count": int(word_count) if isinstance(word_count, (int, float)) else None,
            "language": _clean_text(str(language) if language is not None else None, max_len=50),
            "finalized_at": result.finalized_at.isoformat() if result.finalized_at else None,
            "char_count": int(char_count) if isinstance(char_count, (int, float)) else None,
        })
    return rows
