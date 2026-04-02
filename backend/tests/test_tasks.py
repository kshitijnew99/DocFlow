"""
Unit tests for processing logic — no Celery broker needed.
"""
import pytest
from app.workers.tasks import _parse_file, _extract_fields, _detect_language
import tempfile
import os


def write_temp(content: str, suffix: str = ".txt") -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
    f.write(content)
    f.flush()
    return f.name


# ── _detect_language ──────────────────────────────────────────────────────────

def test_detect_english():
    text = "The quick brown fox jumps over the lazy dog and it is a great day."
    assert _detect_language(text) == "en"


def test_detect_empty():
    assert _detect_language("") == "unknown"
    assert _detect_language("   ") == "unknown"


# ── _parse_file ───────────────────────────────────────────────────────────────

def test_parse_txt_file():
    path = write_temp("Hello world this is a test document.", ".txt")
    try:
        result = _parse_file(path, ".txt", "test.txt")
        assert result["word_count"] == 7
        assert result["char_count"] > 0
        assert "Hello world" in result["raw_text"]
    finally:
        os.unlink(path)


def test_parse_json_file():
    path = write_temp('{"key": "value", "number": 42}', ".json")
    try:
        result = _parse_file(path, ".json", "data.json")
        assert result["char_count"] > 0
        assert "key" in result["raw_text"]
    finally:
        os.unlink(path)


def test_parse_missing_file():
    result = _parse_file("/nonexistent/path/file.txt", ".txt", "missing.txt")
    assert "Binary or unreadable" in result["raw_text"] or result["word_count"] == 0


# ── _extract_fields ───────────────────────────────────────────────────────────

def test_extract_title_from_first_line():
    text = "My Great Document\nThis is the body of the document with more content."
    result = _extract_fields(text, "doc.txt", ".txt")
    assert result["title"] == "My Great Document"


def test_extract_summary_truncated():
    text = "A" * 500
    result = _extract_fields(text, "long.txt", ".txt")
    assert result["summary"].endswith("...")
    assert len(result["summary"]) <= 310


def test_extract_keywords_not_stopwords():
    text = "Python programming language is used for machine learning and data science."
    result = _extract_fields(text, "tech.txt", ".txt")
    keywords = result["keywords"]
    assert "python" in keywords or "Python" in [k.lower() for k in keywords]
    # stopwords should not appear
    assert "the" not in keywords
    assert "is" not in keywords


def test_category_detection_csv():
    result = _extract_fields("col1,col2\n1,2", "data.csv", ".csv")
    assert "Data" in result["category"] or "Spreadsheet" in result["category"]


def test_category_detection_code():
    text = "def my_function():\n    import os\n    return os.getcwd()"
    result = _extract_fields(text, "script.py", ".txt")
    assert "Code" in result["category"] or "Technical" in result["category"]


def test_category_detection_invoice():
    text = "Invoice #1234\nAmount Due: $500\nPayment due in 30 days. Total: $500."
    result = _extract_fields(text, "invoice.txt", ".txt")
    assert "Finance" in result["category"] or "Invoice" in result["category"]


def test_category_detection_academic():
    text = """Abstract
    This paper presents a novel approach.
    Introduction
    The field has advanced. Conclusion. References."""
    result = _extract_fields(text, "paper.txt", ".txt")
    assert "Research" in result["category"] or "Academic" in result["category"]


def test_language_field_populated():
    text = "The quick brown fox. It is a fine day in the world."
    result = _extract_fields(text, "test.txt", ".txt")
    assert "language" in result
    assert result["language"] in ("en", "unknown")


def test_keywords_max_ten():
    text = " ".join(["word" + str(i) for i in range(100)])
    result = _extract_fields(text, "test.txt", ".txt")
    assert len(result["keywords"]) <= 10
