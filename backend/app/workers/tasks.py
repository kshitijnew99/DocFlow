"""
Background document processing tasks.
Each stage publishes a progress event to Redis Pub/Sub.
"""

import time
from collections import Counter
from datetime import datetime

from celery import Task
from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app
from app.core.config import get_settings
from app.core.redis_client import publish_event, set_job_status

logger = get_task_logger(__name__)
settings = get_settings()
_KEYBERT_MODEL = None

_FALLBACK_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall",
    "it", "its", "this", "that", "these", "those", "i", "we", "you",
    "he", "she", "they", "them", "their", "our", "your", "my",
    "not", "no", "nor", "so", "yet", "both", "either", "neither",
}

_LANG_HINTS = {
    "en": "en",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _emit(job_id: str, event_type: str, stage: str, progress: float,
          message: str, status: str = "processing", metadata: dict = None):
    """Emit a progress event via Redis Pub/Sub and cache the current status."""
    payload = {
        "job_id": job_id,
        "event_type": event_type,
        "stage": stage,
        "progress": progress,
        "message": message,
        "status": status,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    publish_event(job_id, payload)
    set_job_status(job_id, payload)
    logger.info(f"[{job_id}] {event_type}: {message} ({progress:.0%})")


def _db_session():
    """Get a fresh DB session for use inside a worker."""
    from app.core.database import SessionLocal
    return SessionLocal()


def _strip_nul(value: str) -> str:
    """PostgreSQL text/json fields cannot store NUL characters."""
    return value.replace("\x00", "") if "\x00" in value else value


def _sanitize_for_storage(value):
    """Recursively sanitize payloads before persisting to DB."""
    if isinstance(value, str):
        return _strip_nul(value)
    if isinstance(value, list):
        return [_sanitize_for_storage(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize_for_storage(v) for k, v in value.items()}
    return value


def _clean_keyword_list(values: list[str], top_n: int) -> list[str]:
    """Normalize, de-duplicate, and bound keyword list size."""
    out: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = " ".join(str(value).strip().split())
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if len(out) >= top_n:
            break

    return out


def _extract_text_from_pdf(file_path: str, original_filename: str) -> str:
    """Extract text from PDF using pypdf; returns a placeholder on failure."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        chunks: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text:
                chunks.append(page_text)

        text = "\n".join(chunks).strip()
        if text:
            return text
        return f"[PDF text extraction returned empty content: {original_filename}]"
    except Exception as exc:
        logger.warning("PDF parse failed for %s: %s", original_filename, exc)
        return f"[PDF parse failed for '{original_filename}': {exc}]"


def _extract_keywords_frequency(raw_text: str, top_n: int) -> list[str]:
    """Deterministic fallback keyword extraction by token frequency."""
    words = raw_text.split()
    word_freq = Counter(
        w.lower().strip(".,!?;:\"'()[]{}") for w in words
        if len(w) > 3 and w.lower() not in _FALLBACK_STOP_WORDS and w.isalpha()
    )
    return [w for w, _ in word_freq.most_common(top_n)]


def _extract_keywords_yake(raw_text: str, language: str, top_n: int) -> list[str]:
    """YAKE extraction: fast, unsupervised, single-doc focused."""
    import yake

    lan = _LANG_HINTS.get(language, "en")
    extractor = yake.KeywordExtractor(
        lan=lan,
        n=max(1, settings.KEYWORD_NGRAM_MAX),
        top=top_n,
        dedupLim=0.9,
    )
    results = extractor.extract_keywords(raw_text)
    return [kw for kw, _ in results]


def _get_keybert_model():
    """Lazily initialize KeyBERT model once per worker process."""
    global _KEYBERT_MODEL
    if _KEYBERT_MODEL is None:
        from keybert import KeyBERT

        _KEYBERT_MODEL = KeyBERT(model=settings.KEYBERT_MODEL_NAME)
    return _KEYBERT_MODEL


def _extract_keywords_keybert(raw_text: str, language: str, top_n: int) -> list[str]:
    """KeyBERT extraction: semantic relevance via sentence-transformers."""
    model = _get_keybert_model()
    stop_words = "english" if language == "en" else None
    results = model.extract_keywords(
        raw_text,
        keyphrase_ngram_range=(settings.KEYWORD_NGRAM_MIN, settings.KEYWORD_NGRAM_MAX),
        stop_words=stop_words,
        top_n=top_n,
        use_mmr=True,
        diversity=0.5,
    )
    return [kw for kw, _ in results]


def _extract_keywords(raw_text: str, language: str) -> list[str]:
    """Keyword extraction strategy: KeyBERT -> YAKE -> frequency fallback."""
    text = _strip_nul(raw_text or "").strip()
    if not text:
        return []

    lower = text.lower()
    if lower.startswith("[binary") or lower.startswith("[pdf parse failed"):
        return []

    top_n = max(1, settings.KEYWORD_TOP_N)
    strategy = (settings.KEYWORD_EXTRACTOR or "auto").lower()

    if strategy in ("auto", "keybert"):
        try:
            return _clean_keyword_list(_extract_keywords_keybert(text, language, top_n), top_n)
        except Exception as exc:
            logger.warning("KeyBERT extraction failed, falling back: %s", exc)

    if strategy in ("auto", "yake"):
        try:
            return _clean_keyword_list(_extract_keywords_yake(text, language, top_n), top_n)
        except Exception as exc:
            logger.warning("YAKE extraction failed, falling back: %s", exc)

    return _clean_keyword_list(_extract_keywords_frequency(text, top_n), top_n)


def _update_job_db(db, job_id: str, **kwargs):
    from app.models.models import ProcessingJob
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if job:
        for k, v in kwargs.items():
            setattr(job, k, v)
        db.commit()
    return job


def _add_job_event(db, job_id: str, event_type: str, stage: str,
                   progress: float, message: str, metadata: dict = None):
    from app.models.models import JobEvent
    ev = JobEvent(
        job_id=job_id,
        event_type=event_type,
        stage=stage,
        progress=progress,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(ev)
    db.commit()


# ── Processing Logic ──────────────────────────────────────────────────────────

def _parse_file(file_path: str, file_type: str, original_filename: str) -> dict:
    """
    Parse the file and return raw text + basic metadata.
    Supports .txt/.md/.csv/.json/.xml as text and .pdf via pypdf.
    """
    text_extensions = {".txt", ".md", ".csv", ".json", ".xml"}
    ext = (file_type or "").lower()

    if ext == ".pdf":
        text = _extract_text_from_pdf(file_path, original_filename)
    elif ext in text_extensions:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception:
            text = f"[Binary or unreadable text file: {original_filename}]"
    else:
        text = f"[Binary file '{original_filename}' ({ext or 'unknown'}) - text preview unavailable]"

    text = _strip_nul(text)

    return {
        "raw_text": text,
        "char_count": len(text),
        "word_count": len(text.split()) if text.strip() else 0,
    }


def _detect_language(text: str) -> str:
    """Simple heuristic language detection."""
    if not text.strip():
        return "unknown"
    # Very basic — real impl would use langdetect
    common_english = {"the", "is", "and", "a", "to", "of", "in", "it"}
    words = set(text.lower().split()[:200])
    if len(words & common_english) >= 3:
        return "en"
    return "unknown"


def _extract_fields(raw_text: str, original_filename: str, file_type: str) -> dict:
    """
    Extract structured fields from the parsed text.
    Uses simple heuristics — the architecture is what matters, not NLP quality.
    """
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    # Title: first non-empty line, truncated
    title = lines[0][:200] if lines else original_filename

    # Summary: first 300 chars of content
    summary = raw_text[:300].strip() + ("..." if len(raw_text) > 300 else "")

    # Category: based on file type + content signals
    ext_map = {
        ".csv": "Data / Spreadsheet",
        ".json": "Structured Data",
        ".xml": "Markup / Config",
        ".md": "Documentation",
        ".txt": "Plain Text",
        ".pdf": "PDF Document",
    }
    category = ext_map.get(file_type.lower(), "General Document")

    # Upgrade category from content signals
    text_lower = raw_text.lower()
    if any(k in text_lower for k in ["invoice", "payment", "amount due", "total"]):
        category = "Finance / Invoice"
    elif any(k in text_lower for k in ["abstract", "introduction", "conclusion", "references"]):
        category = "Research / Academic"
    elif any(k in text_lower for k in ["class", "function", "def ", "import", "return"]):
        category = "Code / Technical"
    elif any(k in text_lower for k in ["dear", "sincerely", "regards", "subject:"]):
        category = "Correspondence"

    language = _detect_language(raw_text)
    keywords = _extract_keywords(raw_text, language)

    return {
        "title": title,
        "category": category,
        "summary": summary,
        "keywords": keywords,
        "language": language,
    }


# ── Main Celery Task ──────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_document",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_document(self: Task, job_id: str, document_id: str,
                     file_path: str, original_filename: str, file_type: str):
    """
    Full async document processing pipeline.
    Stages: receive → parse → extract → store → complete
    """
    db = _db_session()

    try:
        from app.models.models import JobStatus, ProcessingJob, ExtractedResult
        from datetime import datetime

        # ── Stage 0: Job started ──────────────────────────────────────────
        _update_job_db(db, job_id,
                       status=JobStatus.PROCESSING,
                       current_stage="document_received",
                       progress=0.05,
                       started_at=datetime.utcnow(),
                       celery_task_id=self.request.id)

        _emit(job_id, "job_started", "document_received", 0.05,
              f"Processing started for '{original_filename}'", "processing")
        _add_job_event(db, job_id, "job_started", "document_received",
                       0.05, f"Processing started for '{original_filename}'")
        time.sleep(0.5)

        # ── Stage 1: Parsing ──────────────────────────────────────────────
        _update_job_db(db, job_id, current_stage="parsing_started", progress=0.2)
        _emit(job_id, "document_parsing_started", "parsing_started", 0.2,
              "Parsing document content...")
        _add_job_event(db, job_id, "document_parsing_started", "parsing_started",
                       0.2, "Parsing document content...")
        time.sleep(1.0)

        parse_result = _parse_file(file_path, file_type, original_filename)

        _update_job_db(db, job_id, current_stage="parsing_completed", progress=0.45)
        _emit(job_id, "document_parsing_completed", "parsing_completed", 0.45,
              f"Parsed {parse_result['word_count']} words / {parse_result['char_count']} chars",
              metadata={"word_count": parse_result["word_count"],
                        "char_count": parse_result["char_count"]})
        _add_job_event(db, job_id, "document_parsing_completed", "parsing_completed",
                       0.45, f"Parsed {parse_result['word_count']} words")
        time.sleep(0.5)

        # ── Stage 2: Extraction ───────────────────────────────────────────
        _update_job_db(db, job_id, current_stage="extraction_started", progress=0.55)
        _emit(job_id, "field_extraction_started", "extraction_started", 0.55,
              "Extracting structured fields...")
        _add_job_event(db, job_id, "field_extraction_started", "extraction_started",
                       0.55, "Extracting structured fields...")
        time.sleep(1.2)

        extracted = _extract_fields(
            parse_result["raw_text"], original_filename, file_type
        )
        extracted = _sanitize_for_storage(extracted)
        parse_result = _sanitize_for_storage(parse_result)

        _update_job_db(db, job_id, current_stage="extraction_completed", progress=0.75)
        _emit(job_id, "field_extraction_completed", "extraction_completed", 0.75,
              f"Extracted {len(extracted['keywords'])} keywords; category: {extracted['category']}",
              metadata={"category": extracted["category"],
                        "keywords_count": len(extracted["keywords"])})
        _add_job_event(db, job_id, "field_extraction_completed", "extraction_completed",
                       0.75, "Field extraction complete")
        time.sleep(0.5)

        # ── Stage 3: Store result ─────────────────────────────────────────
        _update_job_db(db, job_id, current_stage="final_result_stored", progress=0.90)
        _emit(job_id, "result_storing", "final_result_stored", 0.90,
              "Saving extracted result to database...")

        structured_data = {
            **extracted,
            **parse_result,
            "document_id": document_id,
            "processed_at": datetime.utcnow().isoformat(),
        }
        structured_data = _sanitize_for_storage(structured_data)
        result_payload = _sanitize_for_storage(
            {
                **extracted,
                **parse_result,
                "structured_data": structured_data,
            }
        )

        # Upsert ExtractedResult
        existing = db.query(ExtractedResult).filter(
            ExtractedResult.job_id == job_id
        ).first()

        if existing:
            for k, v in result_payload.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            existing.structured_data = structured_data
            db.commit()
        else:
            result = ExtractedResult(
                job_id=job_id,
                **{k: v for k, v in result_payload.items()
                   if k in ExtractedResult.__table__.columns.keys()},
            )
            db.add(result)
            db.commit()

        _add_job_event(db, job_id, "result_stored", "final_result_stored",
                       0.90, "Result persisted")
        time.sleep(0.3)

        # ── Stage 4: Complete ─────────────────────────────────────────────
        _update_job_db(db, job_id,
                       status=JobStatus.COMPLETED,
                       current_stage="job_completed",
                       progress=1.0,
                       completed_at=datetime.utcnow())

        _emit(job_id, "job_completed", "job_completed", 1.0,
              f"'{original_filename}' processed successfully", status="completed",
              metadata={"title": extracted["title"], "category": extracted["category"]})
        _add_job_event(db, job_id, "job_completed", "job_completed",
                       1.0, "Job completed successfully")

    except Exception as exc:
        logger.exception(f"[{job_id}] Processing failed: {exc}")

        try:
            db.rollback()
            from app.models.models import JobStatus
            job = db.query(__import__("app.models.models", fromlist=["ProcessingJob"]).ProcessingJob
                           ).filter_by(id=job_id).first()
            retry_count = (job.retry_count if job else 0)
            _update_job_db(db, job_id,
                           status=JobStatus.FAILED,
                           current_stage="job_failed",
                           error_message=_strip_nul(str(exc)),
                           completed_at=datetime.utcnow())
            _emit(job_id, "job_failed", "job_failed", 0.0,
                  f"Processing failed: {exc}", status="failed")
            _add_job_event(db, job_id, "job_failed", "job_failed",
                           0.0, f"Failed: {exc}")
        except Exception:
            pass

        raise

    finally:
        db.close()
