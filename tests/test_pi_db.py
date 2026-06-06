"""Tests for pi database module."""
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lmstudio_db

import pi_db
from pi_db import _extract_tokens, _parse_timestamp, _msg_to_conversation


def test_extract_tokens_full():
    usage = {"input": 1000, "output": 500, "cacheRead": 200, "cacheWrite": 300, "totalTokens": 2000}
    inp, out, reason, cache_read, cache_write = _extract_tokens(usage)
    assert inp == 1000 and out == 500 and reason == 0 and cache_read == 200 and cache_write == 300


def test_extract_tokens_empty():
    inp, out, reason, cache_read, cache_write = _extract_tokens({})
    assert inp == 0 and out == 0 and reason == 0 and cache_read == 0 and cache_write == 0


def test_extract_tokens_zero_values():
    inp, out, reason, cache_read, cache_write = _extract_tokens({"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0})
    assert inp == 0 and out == 0 and reason == 0 and cache_read == 0 and cache_write == 0


def test_extract_tokens_none_input():
    inp, out, reason, cache_read, cache_write = _extract_tokens(None)
    assert inp == 0 and out == 0 and reason == 0 and cache_read == 0 and cache_write == 0


def test_parse_timestamp_iso():
    result = _parse_timestamp("2026-06-06T15:36:15.145Z")
    assert isinstance(result, datetime)


def test_parse_timestamp_none():
    result = _parse_timestamp(None)
    assert result is None


def test_msg_to_conversation_valid():
    line = {
        "type": "message",
        "timestamp": "2026-06-06T15:36:15.145Z",
        "message": {
            "role": "assistant",
            "id": "msg_001",
            "usage": {"input": 100, "output": 200, "cacheRead": 50, "cacheWrite": 10, "totalTokens": 360},
        },
    }
    result = _msg_to_conversation(line)
    assert result is not None
    assert result["source"] == "pi"
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 200
    assert result["cache_read_tokens"] == 50
    assert result["cache_write_tokens"] == 10
    assert result["token_count"] == 360


def test_msg_to_conversation_skips_user():
    line = {"type": "message", "timestamp": "2026-06-06T15:36:15.145Z", "message": {"role": "user", "content": "hello"}}
    assert _msg_to_conversation(line) is None


def test_msg_to_conversation_skips_no_usage():
    line = {"type": "message", "timestamp": "2026-06-06T15:36:15.145Z", "message": {"role": "assistant", "content": "hi"}}
    assert _msg_to_conversation(line) is None


def test_msg_to_conversation_skips_non_message():
    line = {"type": "model_change", "modelId": "gpt-4"}
    assert _msg_to_conversation(line) is None


def test_msg_to_conversation_zero_tokens_skipped():
    line = {
        "type": "message",
        "timestamp": "2026-06-06T15:36:15.145Z",
        "message": {"role": "assistant", "usage": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}},
    }
    assert _msg_to_conversation(line) is None


def test_msg_to_conversation_missing_message_key():
    line = {"type": "session", "id": "abc123"}
    assert _msg_to_conversation(line) is None


def test_sync_pi_tokens_basic():
    """Test syncing assistant messages from mock JSONL session files."""
    tmpdir = tempfile.mkdtemp()

    # Create a mock pi sessions directory with a subdirectory
    sess_dir = os.path.join(tmpdir, "sessions", "--home-takosaga--")
    os.makedirs(sess_dir)

    # Write a JSONL file with mixed message types
    jsonl_path = os.path.join(sess_dir, "2026-06-06T15-36-15_abc123.jsonl")
    messages = [
        {"type": "session", "version": 1, "id": "sess_001"},
        {"type": "message", "timestamp": "2026-06-06T15:36:15.145Z", "message": {
            "role": "user", "content": "hello"
        }},
        {"type": "message", "timestamp": "2026-06-06T15:36:16.200Z", "message": {
            "role": "assistant",
            "id": "msg_001",
            "usage": {"input": 100, "output": 200, "cacheRead": 50, "cacheWrite": 10, "totalTokens": 360},
        }},
        {"type": "message", "timestamp": "2026-06-06T15:36:17.300Z", "message": {
            "role": "assistant",
            "id": "msg_002",
            "usage": {"input": 50, "output": 100, "cacheRead": 0, "cacheWrite": 0},
        }},
        {"type": "message", "timestamp": "2026-06-06T15:36:18.400Z", "message": {
            "role": "assistant",
            "id": "msg_zero",
            "usage": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        }},
    ]
    with open(jsonl_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    # Create lmstudio_usage.db
    lmstudio_db_path = os.path.join(tmpdir, "lmstudio_usage.db")
    lmstudio_db.init_db(lmstudio_db_path)

    synced = pi_db.sync_pi_tokens(
        db_path=os.path.join(tmpdir, "sessions"),
        lmstudio_db_path=lmstudio_db_path,
    )

    assert synced == 2  # msg_001 and msg_002 (user and zero-token skipped)

    # Verify data in DB
    import sqlite3
    conn = sqlite3.connect(lmstudio_db_path)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM conversations WHERE source = 'pi'")
    assert c.fetchone()[0] == 2

    # Check msg_001
    c.execute(
        "SELECT model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, token_count "
        "FROM conversations WHERE filename LIKE '%msg_001%'"
    )
    row = c.fetchone()
    assert row is not None
    assert row[0] == ""  # no modelId in test data
    assert row[1] == 100
    assert row[2] == 200
    assert row[3] == 50
    assert row[4] == 10
    assert row[5] == 360

    # Check msg_002
    c.execute(
        "SELECT input_tokens, output_tokens, cache_write_tokens FROM conversations WHERE filename LIKE '%msg_002%'"
    )
    row = c.fetchone()
    assert row is not None
    assert row[0] == 50
    assert row[1] == 100

    conn.close()


def test_sync_pi_tokens_no_sessions_dir():
    """Test graceful handling when sessions directory doesn't exist."""
    synced = pi_db.sync_pi_tokens(
        db_path="/nonexistent/pi/sessions"
    )
    assert synced == 0
