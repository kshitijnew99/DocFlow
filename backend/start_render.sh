#!/usr/bin/env bash
set -euo pipefail

# If tables already exist but Alembic metadata is missing/incomplete, stamp once and continue.
needs_stamp=$(python - <<'PY'
from sqlalchemy import create_engine, inspect, text
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.DATABASE_URL)
tables = set(inspect(engine).get_table_names())

if "documents" not in tables:
	print("no")
elif "alembic_version" not in tables:
	print("yes")
else:
	with engine.connect() as conn:
		version_rows = conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar_one()
	print("yes" if version_rows == 0 else "no")
PY
)

if [[ "$needs_stamp" == "yes" ]]; then
	echo "Existing schema detected without alembic_version. Stamping migration head..."
	alembic stamp head
fi

# Apply DB migrations before starting the API process.
# If initial migration re-runs against an existing schema, stamp and continue.
if ! alembic upgrade head; then
	echo "Alembic upgrade failed. Checking for existing base schema..."
	has_documents=$(python - <<'PY'
from sqlalchemy import create_engine, inspect
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.DATABASE_URL)
tables = set(inspect(engine).get_table_names())
print("yes" if "documents" in tables else "no")
PY
)

	if [[ "$has_documents" == "yes" ]]; then
		echo "Existing documents table found. Stamping migration head and continuing startup..."
		alembic stamp head
	else
		echo "Migration failed and base schema was not detected. Aborting startup."
		exit 1
	fi
fi

# Start Celery worker in the background so uploaded files can be processed.
celery -A app.workers.celery_app worker --loglevel=info --concurrency="${CELERY_CONCURRENCY:-2}" &

# Run FastAPI on Render-assigned port.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
