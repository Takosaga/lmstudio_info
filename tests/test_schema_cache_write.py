"""Tests for cache_write_tokens schema column."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lmstudio_db


def test_init_db_creates_cache_write_column():
    """Verify init_db creates the cache_write_tokens column."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    lmstudio_db.init_db(db_path)

    conn = __import__("sqlite3").connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(conversations)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "cache_write_tokens" in columns
    conn.close()


def test_upsert_with_cache_write_tokens():
    """Verify upsert_conversation handles cache_write_tokens field."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    lmstudio_db.init_db(db_path)

    conv = {
        "filename": "test_file.json",
        "token_count": 1000,
        "message_count": 2,
        "model": "test-model",
        "created_at": "2026-06-06T12:00:00",
        "user_last_message_at": "2026-06-06T12:05:00",
        "source": "pi",
        "input_tokens": 500,
        "output_tokens": 300,
        "reasoning_tokens": 0,
        "cache_read_tokens": 100,
        "cache_write_tokens": 200,
        "tool_call_count": 0,
    }
    lmstudio_db.upsert_conversation(db_path, conv)

    conn = __import__("sqlite3").connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT cache_write_tokens FROM conversations WHERE filename = ?",
        ("test_file.json",),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == 200
    conn.close()
