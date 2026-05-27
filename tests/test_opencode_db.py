"""Tests for OpenCode database module."""
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import opencode_db
import lmstudio_db


def _create_mock_opencode_db(tmpdir):
    """Create a minimal opencode.db with test data.

    Returns the path to the created database.
    """
    db_path = os.path.join(tmpdir, "opencode_test.db")
    conn = __import__("sqlite3").connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE message (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            time_created INTEGER NOT NULL,
            time_updated INTEGER NOT NULL,
            data TEXT NOT NULL
        )
    """)

    # Assistant message with tokens
    c.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        (
            "msg_test_001",
            "sess_abc",
            1764334238483,
            1764334240000,
            json.dumps({
                "role": "assistant",
                "time": {"created": 1764334238483},
                "modelID": "big-pickle",
                "providerID": "opencode",
                "tokens": {
                    "input": 94,
                    "output": 48,
                    "reasoning": 0,
                    "cache": {"read": 10560, "write": 0}
                }
            }),
        ),
    )

    # Assistant message with zero tokens (should be filtered)
    c.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        (
            "msg_test_002",
            "sess_abc",
            1764334250000,
            1764334251000,
            json.dumps({
                "role": "assistant",
                "time": {"created": 1764334250000},
                "modelID": "big-pickle",
                "tokens": {"input": 0, "output": 0, "reasoning": 0, "cache": {"read": 0, "write": 0}}
            }),
        ),
    )

    # User message (should be filtered)
    c.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        (
            "msg_test_003",
            "sess_abc",
            1764334200000,
            1764334210000,
            json.dumps({
                "role": "user",
                "time": {"created": 1764334200000},
                "model": {"providerID": "opencode", "modelID": "big-pickle"}
            }),
        ),
    )

    # Assistant message with reasoning tokens
    c.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        (
            "msg_test_004",
            "sess_def",
            1764335000000,
            1764335100000,
            json.dumps({
                "role": "assistant",
                "time": {"created": 1764335000000},
                "modelID": "test-reasoning-model",
                "providerID": "opencode",
                "tokens": {
                    "input": 100,
                    "output": 200,
                    "reasoning": 50,
                    "cache": {"read": 10, "write": 0}
                }
            }),
        ),
    )

    conn.commit()
    conn.close()
    return db_path


def test_sync_opencode_tokens_basic():
    """Test syncing assistant messages with tokens from opencode.db."""
    tmpdir = tempfile.mkdtemp()

    # Create mock opencode.db
    opencode_db_path = _create_mock_opencode_db(tmpdir)

    # Create lmstudio_usage.db
    lmstudio_db_path = os.path.join(tmpdir, "lmstudio_usage.db")
    lmstudio_db.init_db(lmstudio_db_path)

    synced = opencode_db.sync_opencode_tokens(
        db_path=opencode_db_path,
        lmstudio_db_path=lmstudio_db_path
    )

    assert synced == 2  # msg_test_001 and msg_test_004 (assistant with tokens)

    # Verify data in lmstudio_usage.db
    conn = __import__("sqlite3").connect(lmstudio_db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM conversations WHERE source = 'opencode'")
    count = c.fetchone()[0]
    assert count == 2

    # Check msg_test_001 data
    c.execute(
        "SELECT model, token_count, input_tokens, output_tokens, cache_read_tokens "
        "FROM conversations WHERE filename = 'msg_test_001'"
    )
    row = c.fetchone()
    assert row is not None
    assert row[0] == "big-pickle"
    assert row[1] == 94 + 48 + 0 + 10560  # total_tokens
    assert row[2] == 94   # input
    assert row[3] == 48   # output
    assert row[4] == 10560  # cache_read

    # Check msg_test_004 with reasoning tokens
    c.execute(
        "SELECT model, token_count, reasoning_tokens FROM conversations WHERE filename = 'msg_test_004'"
    )
    row = c.fetchone()
    assert row is not None
    assert row[0] == "test-reasoning-model"
    assert row[1] == 100 + 200 + 50 + 10  # total_tokens
    assert row[2] == 50  # reasoning

    conn.close()


def test_sync_opencode_tokens_missing_db():
    """Test graceful handling when opencode.db doesn't exist."""
    synced = opencode_db.sync_opencode_tokens(
        db_path="/nonexistent/path/opencode.db"
    )
    assert synced == 0


def test_sync_opencode_tokens_filters_zero_tokens():
    """Verify assistant messages with zero tokens are excluded."""
    tmpdir = tempfile.mkdtemp()

    opencode_db_path = _create_mock_opencode_db(tmpdir)
    lmstudio_db_path = os.path.join(tmpdir, "lmstudio_usage.db")
    lmstudio_db.init_db(lmstudio_db_path)

    synced = opencode_db.sync_opencode_tokens(
        db_path=opencode_db_path,
        lmstudio_db_path=lmstudio_db_path
    )

    assert synced == 2

    # Verify the zero-token assistant message was NOT inserted
    conn = __import__("sqlite3").connect(lmstudio_db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM conversations WHERE filename = 'msg_test_002'")
    assert c.fetchone()[0] == 0

    # Verify the user message was NOT inserted
    c.execute("SELECT COUNT(*) FROM conversations WHERE filename = 'msg_test_003'")
    assert c.fetchone()[0] == 0

    conn.close()


def test_sync_opencode_tokens_upsert_existing():
    """Test that re-syncing doesn't create duplicates."""
    tmpdir = tempfile.mkdtemp()

    opencode_db_path = _create_mock_opencode_db(tmpdir)
    lmstudio_db_path = os.path.join(tmpdir, "lmstudio_usage.db")
    lmstudio_db.init_db(lmstudio_db_path)

    # First sync
    synced1 = opencode_db.sync_opencode_tokens(db_path=opencode_db_path, lmstudio_db_path=lmstudio_db_path)
    assert synced1 == 2

    # Second sync (should not duplicate)
    synced2 = opencode_db.sync_opencode_tokens(db_path=opencode_db_path, lmstudio_db_path=lmstudio_db_path)
    assert synced2 == 2

    # Verify only 2 rows exist
    conn = __import__("sqlite3").connect(lmstudio_db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM conversations WHERE source = 'opencode'")
    count = c.fetchone()[0]
    assert count == 2

    conn.close()


def test_extract_tokens():
    """Test token extraction from data JSON."""
    data_with_all = {
        "tokens": {
            "input": 100,
            "output": 200,
            "reasoning": 30,
            "cache": {"read": 50, "write": 10}
        }
    }
    inp, out, reason, cache = opencode_db._extract_tokens(data_with_all)
    assert inp == 100
    assert out == 200
    assert reason == 30
    assert cache == 50

    # Missing tokens key
    data_no_tokens = {}
    inp, out, reason, cache = opencode_db._extract_tokens(data_no_tokens)
    assert inp == 0 and out == 0 and reason == 0 and cache == 0


def test_parse_timestamp_ms():
    """Test millisecond timestamp parsing."""
    # Millisecond timestamp (> year 2100 threshold)
    result = opencode_db._parse_timestamp_ms(1764334238483)
    assert isinstance(result, datetime)

    # Second timestamp (< threshold)
    result2 = opencode_db._parse_timestamp_ms(1709251200)
    assert isinstance(result2, datetime)

    # None input
    result3 = opencode_db._parse_timestamp_ms(None)
    assert result3 is None


def test_row_to_conversation_skips_user():
    """Test that user messages are skipped."""
    row = (
        "msg_user",
        1764334200000,
        json.dumps({"role": "user", "model": {"modelID": "test"}}),
    )
    result = opencode_db._row_to_conversation(row)
    assert result is None


def test_row_to_conversation_skips_zero_tokens():
    """Test that assistant messages with zero tokens are skipped."""
    row = (
        "msg_zero",
        1764334250000,
        json.dumps({
            "role": "assistant",
            "modelID": "test-model",
            "tokens": {"input": 0, "output": 0, "reasoning": 0, "cache": {"read": 0}}
        }),
    )
    result = opencode_db._row_to_conversation(row)
    assert result is None


def test_row_to_conversation_skips_no_model():
    """Test that assistant messages without modelID are skipped."""
    row = (
        "msg_nodel",
        1764334250000,
        json.dumps({
            "role": "assistant",
            "tokens": {"input": 10, "output": 5, "reasoning": 0, "cache": {"read": 0}}
        }),
    )
    result = opencode_db._row_to_conversation(row)
    assert result is None


def test_row_to_conversation_handles_bad_json():
    """Test that malformed JSON in data column is handled."""
    row = ("msg_bad", 1764334250000, "not valid json{{{")
    result = opencode_db._row_to_conversation(row)
    assert result is None


def _create_mock_opencode_db_with_parts(tmpdir):
    """Create a minimal opencode.db with part table and test data.

    Returns the path to the created database.
    """
    db_path = os.path.join(tmpdir, "opencode_test_parts.db")
    conn = __import__("sqlite3").connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE message (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            time_created INTEGER NOT NULL,
            time_updated INTEGER NOT NULL,
            data TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE part (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            "index" INTEGER NOT NULL,
            data TEXT NOT NULL
        )
    """)

    # Assistant message with 2 tool calls
    c.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        (
            "msg_tool_001",
            "sess_abc",
            1764334238483,
            1764334240000,
            json.dumps({
                "role": "assistant",
                "modelID": "test-model",
                "tokens": {"input": 94, "output": 48, "reasoning": 0, "cache": {"read": 0}}
            }),
        ),
    )
    # Two tool parts linked to msg_tool_001
    c.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?)",
        ("part_001", "msg_tool_001", 0, json.dumps({"type": "tool", "callID": "call_1", "tool": "glob"})),
    )
    c.execute(
        "INSERT INTO part VALUES (?, ?, ?, ?)",
        ("part_002", "msg_tool_001", 1, json.dumps({"type": "tool", "callID": "call_2", "tool": "read_file"})),
    )

    # Assistant message with no tool calls
    c.execute(
        "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
        (
            "msg_tool_002",
            "sess_def",
            1764335000000,
            1764335100000,
            json.dumps({
                "role": "assistant",
                "modelID": "test-model",
                "tokens": {"input": 100, "output": 200, "reasoning": 0, "cache": {"read": 0}}
            }),
        ),
    )

    conn.commit()
    conn.close()
    return db_path


def test_sync_opencode_tokens_with_tool_calls():
    """Test syncing assistant messages with tool call counts from part table."""
    tmpdir = tempfile.mkdtemp()

    opencode_db_path = _create_mock_opencode_db_with_parts(tmpdir)
    lmstudio_db_path = os.path.join(tmpdir, "lmstudio_usage.db")
    lmstudio_db.init_db(lmstudio_db_path)

    synced = opencode_db.sync_opencode_tokens(
        db_path=opencode_db_path,
        lmstudio_db_path=lmstudio_db_path
    )

    assert synced == 2

    conn = __import__("sqlite3").connect(lmstudio_db_path)
    c = conn.cursor()

    # msg_tool_001 should have 2 tool calls
    c.execute("SELECT tool_call_count FROM conversations WHERE filename = 'msg_tool_001'")
    assert c.fetchone()[0] == 2

    # msg_tool_002 should have 0 tool calls
    c.execute("SELECT tool_call_count FROM conversations WHERE filename = 'msg_tool_002'")
    assert c.fetchone()[0] == 0

    conn.close()
