"""Idempotent schema compatibility fixes for legacy/stamped databases."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_schema_compatibility(engine: Engine) -> None:
    """
    Ensure required tables/columns exist for the current ORM model.

    This is intentionally conservative and idempotent for production startup
    where older databases may have been stamped in Alembic without full schema
    parity.
    """
    with engine.begin() as conn:
        existing_tables = set(inspect(conn).get_table_names())

        if "documents" in existing_tables:
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS filename VARCHAR(500)"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS original_filename VARCHAR(500)"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_path VARCHAR(1000)"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_size INTEGER"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_type VARCHAR(100)"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS mime_type VARCHAR(200)"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMP"))
            conn.execute(text("UPDATE documents SET uploaded_at = NOW() WHERE uploaded_at IS NULL"))
            conn.execute(text("ALTER TABLE documents ALTER COLUMN uploaded_at SET DEFAULT NOW()"))

        if "processing_jobs" in existing_tables:
            conn.execute(text("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR(200)"))
            conn.execute(text("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS status VARCHAR(20)"))
            conn.execute(text("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS current_stage VARCHAR(100)"))
            conn.execute(text("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS progress DOUBLE PRECISION"))
            conn.execute(text("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS error_message TEXT"))
            conn.execute(text("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS retry_count INTEGER"))
            conn.execute(text("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS max_retries INTEGER"))
            conn.execute(text("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP"))
            conn.execute(text("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS started_at TIMESTAMP"))
            conn.execute(text("ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP"))
            conn.execute(text("UPDATE processing_jobs SET status = 'queued' WHERE status IS NULL"))
            conn.execute(text("UPDATE processing_jobs SET progress = 0.0 WHERE progress IS NULL"))
            conn.execute(text("UPDATE processing_jobs SET retry_count = 0 WHERE retry_count IS NULL"))
            conn.execute(text("UPDATE processing_jobs SET max_retries = 3 WHERE max_retries IS NULL"))
            conn.execute(text("UPDATE processing_jobs SET created_at = NOW() WHERE created_at IS NULL"))
            conn.execute(text("ALTER TABLE processing_jobs ALTER COLUMN progress SET DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE processing_jobs ALTER COLUMN retry_count SET DEFAULT 0"))
            conn.execute(text("ALTER TABLE processing_jobs ALTER COLUMN max_retries SET DEFAULT 3"))
            conn.execute(text("ALTER TABLE processing_jobs ALTER COLUMN created_at SET DEFAULT NOW()"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_processing_jobs_status ON processing_jobs (status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_processing_jobs_document_id ON processing_jobs (document_id)"))

        if "extracted_results" in existing_tables:
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS title VARCHAR(500)"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS category VARCHAR(200)"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS summary TEXT"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS keywords JSONB"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS raw_text TEXT"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS word_count INTEGER"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS char_count INTEGER"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS language VARCHAR(50)"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS reviewed_data JSONB"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS structured_data JSONB"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS is_finalized BOOLEAN"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMP"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS created_at TIMESTAMP"))
            conn.execute(text("ALTER TABLE extracted_results ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP"))
            conn.execute(text("UPDATE extracted_results SET is_finalized = FALSE WHERE is_finalized IS NULL"))
            conn.execute(text("UPDATE extracted_results SET created_at = NOW() WHERE created_at IS NULL"))
            conn.execute(text("UPDATE extracted_results SET updated_at = NOW() WHERE updated_at IS NULL"))
            conn.execute(text("ALTER TABLE extracted_results ALTER COLUMN is_finalized SET DEFAULT FALSE"))
            conn.execute(text("ALTER TABLE extracted_results ALTER COLUMN created_at SET DEFAULT NOW()"))
            conn.execute(text("ALTER TABLE extracted_results ALTER COLUMN updated_at SET DEFAULT NOW()"))

        if "job_events" in existing_tables:
            conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'job_events'
                              AND column_name = 'event_metadata'
                        )
                        AND NOT EXISTS (
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'job_events'
                              AND column_name = 'metadata'
                        ) THEN
                            ALTER TABLE job_events RENAME COLUMN event_metadata TO metadata;
                        END IF;
                    END $$;
                    """
                )
            )
            conn.execute(text("ALTER TABLE job_events ADD COLUMN IF NOT EXISTS event_type VARCHAR(100)"))
            conn.execute(text("ALTER TABLE job_events ADD COLUMN IF NOT EXISTS stage VARCHAR(100)"))
            conn.execute(text("ALTER TABLE job_events ADD COLUMN IF NOT EXISTS message TEXT"))
            conn.execute(text("ALTER TABLE job_events ADD COLUMN IF NOT EXISTS metadata JSONB"))
            conn.execute(text("ALTER TABLE job_events ADD COLUMN IF NOT EXISTS occurred_at TIMESTAMP"))
            conn.execute(text("ALTER TABLE job_events ADD COLUMN IF NOT EXISTS progress DOUBLE PRECISION"))
            conn.execute(text("UPDATE job_events SET progress = 0.0 WHERE progress IS NULL"))
            conn.execute(text("UPDATE job_events SET occurred_at = NOW() WHERE occurred_at IS NULL"))
            conn.execute(text("ALTER TABLE job_events ALTER COLUMN progress SET DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE job_events ALTER COLUMN occurred_at SET DEFAULT NOW()"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_job_events_job_id ON job_events (job_id)"))