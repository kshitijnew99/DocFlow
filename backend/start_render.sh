#!/usr/bin/env bash
set -euo pipefail

# If tables already exist but Alembic metadata is missing, stamp once and continue.
needs_stamp=$(python - <<'PY'
from sqlalchemy import create_engine, inspect
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.DATABASE_URL)
tables = set(inspect(engine).get_table_names())

print("yes" if "documents" in tables and "alembic_version" not in tables else "no")
PY
)

if [[ "$needs_stamp" == "yes" ]]; then
	echo "Existing schema detected without alembic_version. Stamping migration head..."
	alembic stamp head
fi

# Apply DB migrations before starting the API process.
alembic upgrade head

# Start Celery worker in the background so uploaded files can be processed.
celery -A app.workers.celery_app worker --loglevel=info --concurrency="${CELERY_CONCURRENCY:-2}" &

# Run FastAPI on Render-assigned port.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
