"""
Integration tests for the DocFlow API.
Run with:  pytest tests/ -v

Uses SQLite in-memory — no running infrastructure required.
Celery tasks are mocked; Redis is mocked where needed.
"""
import json
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# ── In-memory SQLite engine ───────────────────────────────────────────────────

engine = create_engine(
    "sqlite:///./test_docflow.db",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine,
    expire_on_commit=False,
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


# ── Raw-SQL seed (avoids ORM UUID issues on SQLite) ───────────────────────────

def seed_completed_job():
    """Insert doc + completed job + result via raw SQL."""
    doc_id  = str(uuid.uuid4())
    job_id  = str(uuid.uuid4())
    res_id  = str(uuid.uuid4())
    now     = datetime.utcnow().isoformat()

    db = TestingSessionLocal()
    db.execute(text("""
        INSERT INTO documents
            (id, filename, original_filename, file_path,
             file_size, file_type, mime_type, uploaded_at)
        VALUES (:id, :fn, :ofn, :fp, :fs, :ft, :mt, :ua)
    """), dict(id=doc_id, fn="seeded.txt", ofn="seeded.txt",
               fp="/tmp/seeded.txt", fs=100, ft=".txt",
               mt="text/plain", ua=now))

    db.execute(text("""
        INSERT INTO processing_jobs
            (id, document_id, status, progress,
             current_stage, retry_count, max_retries,
             created_at, started_at, completed_at)
        VALUES (:id,:did,'COMPLETED',1.0,'job_completed',0,3,:ca,:sa,:co)
    """), dict(id=job_id, did=doc_id, ca=now, sa=now, co=now))

    db.execute(text("""
        INSERT INTO extracted_results
            (id, job_id, title, category, summary,
             keywords, raw_text, word_count, char_count,
             language, structured_data, is_finalized,
             created_at, updated_at)
        VALUES (:id,:jid,:ti,:ca,:su,:kw,:rt,:wc,:cc,:la,:sd,0,:now,:now)
    """), dict(id=res_id, jid=job_id,
               ti="Seeded Doc", ca="Plain Text", su="A seeded doc.",
               kw=json.dumps(["seed","test"]), rt="Hello world",
               wc=2, cc=11, la="en", sd=json.dumps({"test": True}),
               now=now))
    db.commit()
    db.close()
    return doc_id, job_id, res_id


def seed_failed_job(retry_count=0, max_retries=3):
    """Insert doc + failed job via raw SQL."""
    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    now    = datetime.utcnow().isoformat()

    db = TestingSessionLocal()
    db.execute(text("""
        INSERT INTO documents
            (id, filename, original_filename, file_path,
             file_size, file_type, mime_type, uploaded_at)
        VALUES (:id,'f.txt','f.txt','/tmp/f.txt',10,'.txt','text/plain',:now)
    """), dict(id=doc_id, now=now))

    db.execute(text("""
        INSERT INTO processing_jobs
            (id, document_id, status, progress,
             retry_count, max_retries, error_message,
             created_at, completed_at)
        VALUES (:id,:did,'FAILED',0.0,:rc,:mr,'boom',:now,:now)
    """), dict(id=job_id, did=doc_id, rc=retry_count, mr=max_retries,
               now=now))
    db.commit()
    db.close()
    return doc_id, job_id


# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "DocFlow" in r.json()["service"]


# ── Upload ────────────────────────────────────────────────────────────────────

def test_upload_no_files():
    r = client.post("/api/v1/upload")
    assert r.status_code == 422


def test_upload_bad_extension(tmp_path):
    bad = tmp_path / "evil.exe"
    bad.write_bytes(b"MZ")
    with open(bad, "rb") as f:
        r = client.post("/api/v1/upload",
                        files=[("files", ("evil.exe", f, "application/octet-stream"))])
    assert r.status_code in (415, 422, 500)


# ── List documents ────────────────────────────────────────────────────────────

def test_list_empty():
    r = client.get("/api/v1/documents")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1


def test_list_pagination():
    r = client.get("/api/v1/documents?page=1&page_size=5")
    assert r.status_code == 200
    assert r.json()["page_size"] == 5


def test_list_invalid_page():
    assert client.get("/api/v1/documents?page=0").status_code == 422


def test_list_invalid_sort_dir():
    assert client.get("/api/v1/documents?sort_dir=random").status_code == 422


def test_list_sort_asc():
    assert client.get("/api/v1/documents?sort_dir=asc").status_code == 200


def test_list_with_data():
    seed_completed_job()
    r = client.get("/api/v1/documents")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["original_filename"] == "seeded.txt"


def test_list_search_hit():
    seed_completed_job()
    r = client.get("/api/v1/documents?search=seeded")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_list_search_miss():
    seed_completed_job()
    r = client.get("/api/v1/documents?search=nonexistent_xyz")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_list_status_filter_hit():
    seed_completed_job()
    r = client.get("/api/v1/documents?status=COMPLETED")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_list_status_filter_miss():
    seed_completed_job()
    r = client.get("/api/v1/documents?status=FAILED")
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ── Job detail ────────────────────────────────────────────────────────────────

def test_job_not_found():
    r = client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert r.status_code == 404


def test_job_detail():
    _, job_id, _ = seed_completed_job()
    r = client.get(f"/api/v1/jobs/{job_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == job_id
    assert data["status"] == "completed"
    assert data["progress"] == 1.0
    assert data["result"]["title"] == "Seeded Doc"
    assert data["result"]["keywords"] == ["seed", "test"]


def test_job_detail_includes_events():
    _, job_id, _ = seed_completed_job()
    r = client.get(f"/api/v1/jobs/{job_id}")
    assert r.status_code == 200
    assert isinstance(r.json()["events"], list)


def test_job_detail_includes_document():
    _, job_id, _ = seed_completed_job()
    r = client.get(f"/api/v1/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["document"]["original_filename"] == "seeded.txt"


# ── Edit result ───────────────────────────────────────────────────────────────

def test_update_result():
    _, job_id, _ = seed_completed_job()
    r = client.patch(f"/api/v1/jobs/{job_id}/result",
                     json={"title": "New Title", "keywords": ["a","b"]})
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "New Title"
    assert data["keywords"] == ["a", "b"]


def test_update_result_partial():
    _, job_id, _ = seed_completed_job()
    r = client.patch(f"/api/v1/jobs/{job_id}/result",
                     json={"category": "Finance"})
    assert r.status_code == 200
    assert r.json()["category"] == "Finance"


def test_update_result_not_found():
    r = client.patch(f"/api/v1/jobs/{uuid.uuid4()}/result",
                     json={"title": "X"})
    assert r.status_code == 404


# ── Finalize ──────────────────────────────────────────────────────────────────

def test_finalize():
    _, job_id, _ = seed_completed_job()
    r = client.post(f"/api/v1/jobs/{job_id}/finalize", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["is_finalized"] is True
    assert data["finalized_at"] is not None


def test_finalize_twice_fails():
    _, job_id, _ = seed_completed_job()
    client.post(f"/api/v1/jobs/{job_id}/finalize", json={})
    r = client.post(f"/api/v1/jobs/{job_id}/finalize", json={})
    assert r.status_code == 400
    assert "finalized" in r.json()["detail"].lower()


def test_edit_after_finalize_fails():
    _, job_id, _ = seed_completed_job()
    client.post(f"/api/v1/jobs/{job_id}/finalize", json={})
    r = client.patch(f"/api/v1/jobs/{job_id}/result", json={"title": "Hack"})
    assert r.status_code == 400
    assert "finalized" in r.json()["detail"].lower()


# ── Retry ─────────────────────────────────────────────────────────────────────

def test_retry_non_failed_job():
    _, job_id, _ = seed_completed_job()
    r = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert r.status_code == 400
    assert "failed" in r.json()["detail"].lower()


def test_retry_failed_job():
    _, job_id = seed_failed_job(retry_count=0)

    with patch("app.workers.tasks.process_document") as mock_task, \
         patch("app.core.redis_client.publish_event"):
        mock_task.apply_async.return_value = MagicMock(id="retry-task-id")
        r = client.post(f"/api/v1/jobs/{job_id}/retry")

    assert r.status_code == 200
    assert r.json()["status"] == "queued"
    assert r.json()["retry_count"] == 1


def test_retry_exhausted():
    _, job_id = seed_failed_job(retry_count=3, max_retries=3)
    r = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert r.status_code == 400
    assert "retries" in r.json()["detail"].lower()


# ── Export ────────────────────────────────────────────────────────────────────

def test_export_invalid_format():
    r = client.post("/api/v1/export", json={"job_ids": [], "format": "xml"})
    assert r.status_code == 422


def test_export_unknown_ids():
    r = client.post("/api/v1/export",
                    json={"job_ids": [str(uuid.uuid4())], "format": "json"})
    assert r.status_code == 200
    assert r.json() == []


def test_export_json():
    _, job_id, _ = seed_completed_job()
    r = client.post("/api/v1/export",
                    json={"job_ids": [job_id], "format": "json"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["title"] == "Seeded Doc"
    assert data[0]["job_id"] == job_id


def test_export_csv():
    _, job_id, _ = seed_completed_job()
    r = client.post("/api/v1/export",
                    json={"job_ids": [job_id], "format": "csv"})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "Seeded Doc" in r.text


def test_export_multiple():
    _, jid1, _ = seed_completed_job()
    _, jid2, _ = seed_completed_job()
    r = client.post("/api/v1/export",
                    json={"job_ids": [jid1, jid2], "format": "json"})
    assert r.status_code == 200
    assert len(r.json()) == 2
