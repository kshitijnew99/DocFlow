#!/usr/bin/env bash
set -euo pipefail

# Apply DB migrations before starting the API process.
alembic upgrade head

# Start Celery worker in the background so uploaded files can be processed.
celery -A app.workers.celery_app worker --loglevel=info --concurrency="${CELERY_CONCURRENCY:-2}" &

# Run FastAPI on Render-assigned port.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
