"""Tests for Hermes database module."""
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import hermes_db
import lmstudio_db


def _create_mock_hermes_db(tmpdir):
    """Create a minimal state.db with test session data.

    Returns the path to the created database.
    """
    db_path = os.path.join(tmpdir, "hermes_test.db")
    conn = __import__("sqlite3").connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            user_id TEXT,
            model TEXT,
            model_config TEXT,
            system_prompt TEXT,
            parent_session_id TEXT,
            started_at REAL NOT NULL,
            ended_at REAL,
            end_reason TEXT,
            message_count INTEGER DEFAULT 0,
            tool_call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            reasoning_tokens INTEGER DEFAULT 0,
            billing_provider TEXT,
            billing_base_url TEXT,
            billing_mode TEXT,
            estimated_cost_usd REAL,
            actual_cost_usd REAL,
            cost_status TEXT,
            cost_source TEXT,
            pricing_version TEXT,
            title TEXT,
            api_call_count INTEGER DEFAULT 0,
            handoff_state TEXT,
            handoff_platform TEXT,
            handoff_error TEXT,
            rewind_count INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            FOREIGN KEY (parent_session_id) REFERENCES sessions(id)
        )
    """)

    # Helper: insert session with explicit column names
    def insert_session(sid, src, model, started, ended, msg_count=0,
                       tool_count=0, inp=0, outp=0, cache_r=0,
                       cache_w=0, reason=0, title="", api_calls=0):
        c.execute("""
            INSERT INTO sessions (
                id, source, user_id, model, model_config, system_prompt,
                parent_session_id, started_at, ended_at, end_reason,
                message_count, tool_call_count,
                input_tokens, output_tokens, cache_read_tokens,
                cache_write_tokens, reasoning_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sid, src, None, model, None, None, None,
              started, ended, "cli_close",
              msg_count, tool_count, inp, outp, cache_r,
              cache_w, reason))

    # Session with all token types
    insert_session(
        "20260624_194845_f20214", "cli",
        "qwen3.5-9b-mtp@q4_k_xl",
        1782319725.726, 1782320109.798,
        msg_count=32, tool_count=14,
        inp=316542, outp=2067, title="Where Hermes Stores Session Data",
        api_calls=16
    )

    # Session with reasoning tokens
    insert_session(
        "20260625_100000_aabb11", "cli",
        "test-reasoning-model",
        1782400000.0, 1782401000.0,
        msg_count=10, tool_count=5,
        inp=1000, outp=500, reason=200,
        title="Test reasoning session", api_calls=5
    )

    # Session with cache tokens
    insert_session(
        "20260625_110000_ccdd22", "signal",
        "lmstudio-community/qwen-7b",
        1782403600.0, 1782404000.0,
        msg_count=5, tool_count=2,
        inp=500, outp=300, cache_r=10000, cache_w=500,
        title="Signal chat with cache", api_calls=3
    )

    # Session with zero tokens (should be filtered)
    insert_session(
        "20260625_120000_eeff33", "cli",
        "empty-model",
        1782407200.0, 1782407210.0,
        title="Empty session"
    )

    # Session with no model (should be filtered)
    insert_session(
        "20260625_130000_gg4444", "telegram",
        None,  # no model
        1782410800.0, 1782411000.0,
        msg_count=2, inp=10, outp=5,
        title="No model session", api_calls=1
    )

    conn.commit()
    conn.close()
    return db_path


def test_sync_hermes_tokens_basic():
    """Test syncing sessions from Hermes state.db."""
    tmpdir = tempfile.mkdtemp()

    hermes_db_path = _create_mock_hermes_db(tmpdir)
    lmstudio_db_path = os.path.join(tmpdir, "lmstudio_usage.db")
    lmstudio_db.init_db(lmstudio_db_path)

    synced = hermes_db.sync_hermes_tokens(
        db_path=hermes_db_path,
        lmstudio_db_path=lmstudio_db_path
    )

    assert synced == 3  # 3 sessions with tokens (zero-token and no-model filtered)

    conn = __import__("sqlite3").connect(lmstudio_db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM conversations WHERE source = 'hermes'")
    count = c.fetchone()[0]
    assert count == 3
    conn.close()


def test_sync_hermes_tokens_missing_db():
    """Test graceful handling when state.db doesn't exist."""
    synced = hermes_db.sync_hermes_tokens(
        db_path="/nonexistent/path/state.db"
    )
    assert synced == 0


def test_sync_hermes_tokens_filters_zero_tokens():
    """Verify sessions with zero tokens are excluded."""
    tmpdir = tempfile.mkdtemp()

    hermes_db_path = _create_mock_hermes_db(tmpdir)
    lmstudio_db_path = os.path.join(tmpdir, "lmstudio_usage.db")
    lmstudio_db.init_db(lmstudio_db_path)

    synced = hermes_db.sync_hermes_tokens(
        db_path=hermes_db_path,
        lmstudio_db_path=lmstudio_db_path
    )

    assert synced == 3

    conn = __import__("sqlite3").connect(lmstudio_db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM conversations WHERE filename = '20260625_120000_eeff33'")
    assert c.fetchone()[0] == 0
    conn.close()


def test_sync_hermes_tokens_filters_no_model():
    """Verify sessions without a model are excluded."""
    tmpdir = tempfile.mkdtemp()

    hermes_db_path = _create_mock_hermes_db(tmpdir)
    lmstudio_db_path = os.path.join(tmpdir, "lmstudio_usage.db")
    lmstudio_db.init_db(lmstudio_db_path)

    synced = hermes_db.sync_hermes_tokens(
        db_path=hermes_db_path,
        lmstudio_db_path=lmstudio_db_path
    )

    conn = __import__("sqlite3").connect(lmstudio_db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM conversations WHERE filename = '20260625_130000_gg4444'")
    assert c.fetchone()[0] == 0
    conn.close()


def test_sync_hermes_tokens_upsert_existing():
    """Test that re-syncing doesn't create duplicates."""
    tmpdir = tempfile.mkdtemp()

    hermes_db_path = _create_mock_hermes_db(tmpdir)
    lmstudio_db_path = os.path.join(tmpdir, "lmstudio_usage.db")
    lmstudio_db.init_db(lmstudio_db_path)

    synced1 = hermes_db.sync_hermes_tokens(db_path=hermes_db_path, lmstudio_db_path=lmstudio_db_path)
    assert synced1 == 3

    synced2 = hermes_db.sync_hermes_tokens(db_path=hermes_db_path, lmstudio_db_path=lmstudio_db_path)
    assert synced2 == 3

    conn = __import__("sqlite3").connect(lmstudio_db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM conversations WHERE source = 'hermes'")
    count = c.fetchone()[0]
    assert count == 3
    conn.close()


def test_row_to_conversation_all_token_types():
    """Test conversation dict has correct token breakdown."""
    row = (
        "20260624_194845_f20214", "cli", None, "qwen3.5-9b-mtp@q4_k_xl",
        None, None, None, 1782319725.726, 1782320109.798, "cli_close",
        32, 14, 316542, 2067, 0, 0, 0,
        None, None, None, None, None, None, None, None,
        None, 16, None, None, None, 0, 0
    )
    conv = hermes_db._row_to_conversation(row)

    assert conv is not None
    assert conv["filename"] == "20260624_194845_f20214"
    assert conv["model"] == "qwen3.5-9b-mtp@q4_k_xl"
    assert conv["source"] == "hermes"
    assert conv["input_tokens"] == 316542
    assert conv["output_tokens"] == 2067
    assert conv["token_count"] == 316542 + 2067  # no reasoning/cache in this row
    assert conv["message_count"] == 32
    assert conv["tool_call_count"] == 14


def test_row_to_conversation_reasoning_tokens():
    """Test reasoning token extraction."""
    row = (
        "sess_reason", "cli", None, "test-model",
        None, None, None, 1782400000.0, 1782401000.0, "timeout",
        10, 5, 1000, 500, 0, 0, 200,
        None, None, None, None, None, None, None, None,
        None, 5, None, None, None, 0, 0
    )
    conv = hermes_db._row_to_conversation(row)

    assert conv["reasoning_tokens"] == 200
    assert conv["token_count"] == 1000 + 500 + 200


def test_row_to_conversation_cache_tokens():
    """Test cache token extraction and model name normalization."""
    row = (
        "sess_cache", "signal", None, "lmstudio-community/qwen-7b",
        None, None, None, 1782403600.0, 1782404000.0, "cli_close",
        5, 2, 500, 300, 10000, 500, 0,
        None, None, None, None, None, None, None, None,
        None, 3, None, None, None, 0, 0
    )
    conv = hermes_db._row_to_conversation(row)

    assert conv["model"] == "qwen-7b"  # prefix stripped
    assert conv["cache_read_tokens"] == 10000
    assert conv["cache_write_tokens"] == 500
    assert conv["token_count"] == 500 + 300 + 0 + 10000 + 500


def test_row_to_conversation_skips_no_model():
    """Test that sessions without model are skipped."""
    row = (
        "sess_nomodel", "cli", None, None,
        None, None, None, 1782410800.0, 1782411000.0, "cli_close",
        2, 0, 10, 5, 0, 0, 0,
        None, None, None, None, None, None, None, None,
        None, 1, None, None, None, 0, 0
    )
    result = hermes_db._row_to_conversation(row)
    assert result is None


def test_row_to_conversation_skips_zero_tokens():
    """Test that sessions with zero total tokens are skipped."""
    row = (
        "sess_zero", "cli", None, "empty-model",
        None, None, None, 1782407200.0, 1782407210.0, "empty",
        0, 0, 0, 0, 0, 0, 0,
        None, None, None, None, None, None, None, None,
        None, 0, None, None, None, 0, 0
    )
    result = hermes_db._row_to_conversation(row)
    assert result is None


def test_parse_timestamp():
    """Test Unix timestamp parsing."""
    result = hermes_db._parse_timestamp(1782319725.726)
    assert isinstance(result, datetime)

    # None input
    result_none = hermes_db._parse_timestamp(None)
    assert result_none is None


def test_row_to_conversation_handles_bad_index():
    """Test that malformed rows with too few columns are handled."""
    row = ("short", "cli")
    result = hermes_db._row_to_conversation(row)
    assert result is None
