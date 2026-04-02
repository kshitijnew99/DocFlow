"""Initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("file_type", sa.String(100), nullable=False),
        sa.Column("mime_type", sa.String(200)),
        sa.Column("uploaded_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # processing_jobs
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("celery_task_id", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("current_stage", sa.String(100)),
        sa.Column("progress", sa.Float, server_default="0.0"),
        sa.Column("error_message", sa.Text),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("max_retries", sa.Integer, server_default="3"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
    )
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])
    op.create_index("ix_processing_jobs_document_id", "processing_jobs", ["document_id"])

    # extracted_results
    op.create_table(
        "extracted_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("processing_jobs.id"), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("category", sa.String(200)),
        sa.Column("summary", sa.Text),
        sa.Column("keywords", postgresql.JSON),
        sa.Column("raw_text", sa.Text),
        sa.Column("word_count", sa.Integer),
        sa.Column("char_count", sa.Integer),
        sa.Column("language", sa.String(50)),
        sa.Column("structured_data", postgresql.JSON),
        sa.Column("is_finalized", sa.Boolean, server_default="false"),
        sa.Column("finalized_at", sa.DateTime),
        sa.Column("reviewed_data", postgresql.JSON),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # job_events
    op.create_table(
        "job_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("processing_jobs.id"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("stage", sa.String(100)),
        sa.Column("progress", sa.Float, server_default="0.0"),
        sa.Column("message", sa.Text),
        sa.Column("metadata", postgresql.JSON),
        sa.Column("occurred_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])


def downgrade() -> None:
    op.drop_table("job_events")
    op.drop_table("extracted_results")
    op.drop_table("processing_jobs")
    op.drop_table("documents")
