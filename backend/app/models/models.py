import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime, JSON,
    Enum as SAEnum, ForeignKey, Boolean
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    FINALIZED = "finalized"


class ProcessingStage(str, enum.Enum):
    RECEIVED = "document_received"
    PARSING_STARTED = "parsing_started"
    PARSING_COMPLETED = "parsing_completed"
    EXTRACTION_STARTED = "extraction_started"
    EXTRACTION_COMPLETED = "extraction_completed"
    RESULT_STORED = "final_result_stored"
    COMPLETED = "job_completed"
    FAILED = "job_failed"


def _uuid():
    return str(uuid.uuid4())


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=_uuid)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(100), nullable=False)
    mime_type = Column(String(200))
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("ProcessingJob", back_populates="document", uselist=False)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    celery_task_id = Column(String(200))
    status = Column(SAEnum(JobStatus, native_enum=False), default=JobStatus.QUEUED, nullable=False)
    current_stage = Column(String(100))
    progress = Column(Float, default=0.0)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    document = relationship("Document", back_populates="job")
    result = relationship("ExtractedResult", back_populates="job", uselist=False)
    events = relationship("JobEvent", back_populates="job", order_by="JobEvent.occurred_at")


class ExtractedResult(Base):
    __tablename__ = "extracted_results"

    id = Column(String(36), primary_key=True, default=_uuid)
    job_id = Column(String(36), ForeignKey("processing_jobs.id"), nullable=False)

    title = Column(String(500))
    category = Column(String(200))
    summary = Column(Text)
    keywords = Column(JSON)
    raw_text = Column(Text)
    word_count = Column(Integer)
    char_count = Column(Integer)
    language = Column(String(50))
    structured_data = Column(JSON)

    is_finalized = Column(Boolean, default=False)
    finalized_at = Column(DateTime)
    reviewed_data = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job = relationship("ProcessingJob", back_populates="result")


class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    job_id = Column(String(36), ForeignKey("processing_jobs.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    stage = Column(String(100))
    progress = Column(Float, default=0.0)
    message = Column(Text)
    event_metadata = Column("metadata", JSON)
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("ProcessingJob", back_populates="events")
