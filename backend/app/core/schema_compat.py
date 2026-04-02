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

    def _column_type(conn, table_name: str, column_name: str) -> str | None:
        row = conn.execute(
            text(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).first()
        return row[0] if row else None

    with engine.begin() as conn:
        existing_tables = set(inspect(conn).get_table_names())

        # Create missing core tables first so subsequent backfills/queries are safe.
        if "documents" not in existing_tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS documents (
                        id VARCHAR(36) PRIMARY KEY,
                        filename VARCHAR(500) NOT NULL,
                        original_filename VARCHAR(500) NOT NULL,
                        file_path VARCHAR(1000) NOT NULL,
                        file_size INTEGER NOT NULL,
                        file_type VARCHAR(100) NOT NULL,
                        mime_type VARCHAR(200),
                        uploaded_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            existing_tables.add("documents")

        if "documents" in existing_tables:
            doc_id_type = _column_type(conn, "documents", "id")
            if doc_id_type in {"integer", "bigint", "smallint"}:
                conn.execute(
                    text(
                        "ALTER TABLE documents ALTER COLUMN id TYPE VARCHAR(36) USING id::text"
                    )
                )

            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS filename VARCHAR(500)"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS original_filename VARCHAR(500)"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_path VARCHAR(1000)"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_size INTEGER"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_type VARCHAR(100)"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS mime_type VARCHAR(200)"))
            conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMP"))
            conn.execute(text("UPDATE documents SET filename = 'legacy-document' WHERE filename IS NULL"))
            conn.execute(
                text(
                    "UPDATE documents SET original_filename = COALESCE(original_filename, filename, 'legacy-document') "
                    "WHERE original_filename IS NULL"
                )
            )
            conn.execute(text("UPDATE documents SET file_path = '' WHERE file_path IS NULL"))
            conn.execute(text("UPDATE documents SET file_size = 0 WHERE file_size IS NULL"))
            conn.execute(text("UPDATE documents SET file_type = '' WHERE file_type IS NULL"))
            conn.execute(text("UPDATE documents SET uploaded_at = NOW() WHERE uploaded_at IS NULL"))
            conn.execute(text("ALTER TABLE documents ALTER COLUMN uploaded_at SET DEFAULT NOW()"))

        # Create dependent tables after documents.id type has been normalized.
        doc_id_type = _column_type(conn, "documents", "id")
        doc_fk_sql_type = "VARCHAR(36)"
        if doc_id_type == "uuid":
            doc_fk_sql_type = "UUID"
        elif doc_id_type in {"integer", "bigint", "smallint"}:
            doc_fk_sql_type = "INTEGER"

        if "processing_jobs" not in existing_tables:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS processing_jobs (
                        id VARCHAR(36) PRIMARY KEY,
                        document_id {doc_fk_sql_type} NOT NULL REFERENCES documents(id),
                        celery_task_id VARCHAR(200),
                        status VARCHAR(20) NOT NULL DEFAULT 'queued',
                        current_stage VARCHAR(100),
                        progress DOUBLE PRECISION DEFAULT 0.0,
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                    """
                )
            )
            existing_tables.add("processing_jobs")

        if "extracted_results" not in existing_tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS extracted_results (
                        id VARCHAR(36) PRIMARY KEY,
                        job_id VARCHAR(36) NOT NULL REFERENCES processing_jobs(id),
                        title VARCHAR(500),
                        category VARCHAR(200),
                        summary TEXT,
                        keywords JSONB,
                        raw_text TEXT,
                        word_count INTEGER,
                        char_count INTEGER,
                        language VARCHAR(50),
                        structured_data JSONB,
                        is_finalized BOOLEAN DEFAULT FALSE,
                        finalized_at TIMESTAMP,
                        reviewed_data JSONB,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            existing_tables.add("extracted_results")

        if "job_events" not in existing_tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS job_events (
                        id VARCHAR(36) PRIMARY KEY,
                        job_id VARCHAR(36) NOT NULL REFERENCES processing_jobs(id),
                        event_type VARCHAR(100) NOT NULL,
                        stage VARCHAR(100),
                        progress DOUBLE PRECISION DEFAULT 0.0,
                        message TEXT,
                        metadata JSONB,
                        occurred_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            existing_tables.add("job_events")

        if "processing_jobs" in existing_tables:
            jobs_id_type = _column_type(conn, "processing_jobs", "id")
            if jobs_id_type in {"integer", "bigint", "smallint"}:
                conn.execute(
                    text(
                        "ALTER TABLE processing_jobs ALTER COLUMN id TYPE VARCHAR(36) USING id::text"
                    )
                )

            jobs_doc_id_type = _column_type(conn, "processing_jobs", "document_id")
            if jobs_doc_id_type in {"integer", "bigint", "smallint"}:
                conn.execute(
                    text(
                        "ALTER TABLE processing_jobs ALTER COLUMN document_id TYPE VARCHAR(36) USING document_id::text"
                    )
                )

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