from __future__ import annotations
from typing import Any, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.models import JobStatus


# ── Document Schemas ──────────────────────────────────────────────────────────

class DocumentBase(BaseModel):
    filename: str
    original_filename: str
    file_size: int
    file_type: str
    mime_type: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentResponse(DocumentBase):
    id: str
    uploaded_at: datetime
    job: Optional[JobSummary] = None

    class Config:
        from_attributes = True


# ── Job Schemas ───────────────────────────────────────────────────────────────

class JobSummary(BaseModel):
    id: str
    status: JobStatus
    progress: float
    current_stage: Optional[str] = None
    retry_count: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobEventResponse(BaseModel):
    id: str
    event_type: str
    stage: Optional[str] = None
    progress: float
    message: Optional[str] = None
    metadata: Optional[dict] = Field(default=None, validation_alias="event_metadata")
    occurred_at: datetime

    class Config:
        from_attributes = True


class JobDetailResponse(JobSummary):
    document_id: str
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    max_retries: int
    started_at: Optional[datetime] = None
    document: Optional[DocumentResponse] = None
    result: Optional[ExtractedResultResponse] = None
    events: list[JobEventResponse] = []

    class Config:
        from_attributes = True


# ── Result Schemas ────────────────────────────────────────────────────────────

class ExtractedResultResponse(BaseModel):
    id: str
    title: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[list[str]] = None
    word_count: Optional[int] = None
    char_count: Optional[int] = None
    language: Optional[str] = None
    structured_data: Optional[dict] = None
    is_finalized: bool
    finalized_at: Optional[datetime] = None
    reviewed_data: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UpdateResultRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[list[str]] = None
    reviewed_data: Optional[dict] = None


class FinalizeRequest(BaseModel):
    reviewed_data: Optional[dict] = None


# ── List / Dashboard Schemas ──────────────────────────────────────────────────

class DocumentListItem(BaseModel):
    id: str
    original_filename: str
    file_size: int
    file_type: str
    uploaded_at: datetime
    job: Optional[JobSummary] = None

    class Config:
        from_attributes = True


class PaginatedDocuments(BaseModel):
    items: list[DocumentListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Upload Response ───────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    documents: list[DocumentResponse]
    jobs: list[JobSummary]
    message: str


# ── Progress Event (SSE payload) ──────────────────────────────────────────────

class ProgressEvent(BaseModel):
    job_id: str
    event_type: str
    stage: Optional[str] = None
    progress: float = 0.0
    message: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    timestamp: str


# ── Export ────────────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    job_ids: list[UUID]
    format: str = Field(default="json", pattern="^(json|csv)$")
