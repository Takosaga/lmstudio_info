# Pi Token Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add pi session token usage as a third unified data source alongside lmstudio and opencode by scanning JSONL session files and upserting per-message token data into the existing conversations table.

**Architecture:** A new module `pi_db.py` scans `~/.pi/agent/sessions/**/*.jsonl`, extracts assistant messages with their `usage` fields, and upserts each as a row with `source='pi'`. The schema gains one column (`cache_write_tokens`). The dashboard already supports multi-source filtering — no changes needed there.

**Tech Stack:** Python 3.12, SQLite, pandas, plotly, Shiny, pytest.

---

### Task 1: Add `cache_write_tokens` Column to Schema

**Files:**
- Modify: `lmstudio_db.py` (lines ~67-80, ~149-159, ~273-295)
- Test: `tests/test_schema_cache_write.py`

#### Step 1.1: Write failing tests for schema migration

```python
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
```

#### Step 1.2: Run tests to verify they fail

Run: `uv run pytest tests/test_schema_cache_write.py -v`
Expected: FAIL — `cache_write_tokens` column doesn't exist yet, INSERT statement doesn't include it.

#### Step 1.3: Add `cache_write_tokens` to schema CREATE TABLE (both locations)

In `lmstudio_db.py`, add to the first `CREATE TABLE` in `init_db()` (around line 67):
```sql
                cache_write_tokens INTEGER DEFAULT 0,
```
Place it after `cache_read_tokens INTEGER DEFAULT 0,`.

In `lmstudio_db.py`, add to the second `CREATE TABLE` in `get_or_create_table()` (around line 149):
```sql
                cache_write_tokens INTEGER DEFAULT 0,
```
Place it after `cache_read_tokens INTEGER DEFAULT 0,`.

#### Step 1.4: Add `cache_write_tokens` to migration list (both locations)

In `init_db()`, add to the `new_columns` list:
```python
            ('cache_write_tokens', 'INTEGER DEFAULT 0'),
```
Place it after `('tool_call_count', 'INTEGER DEFAULT 0'),`.

In `get_or_create_table()`, add the same entry to its `new_columns` list.

#### Step 1.5: Update INSERT statement in `upsert_conversation()`

Replace the existing INSERT (around line 273):
```python
            cursor.execute('''
                INSERT INTO conversations (
                    filename, token_count, message_count, model,
                    created_at, user_last_message_at, updated_at,
                    source, input_tokens, output_tokens, reasoning_tokens, cache_read_tokens, tool_call_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                filename,
                conversation_data.get('token_count', 0),
                conversation_data.get('message_count', 0),
                conversation_data.get('model', ''),
                conversation_data.get('created_at'),
                conversation_data.get('user_last_message_at', None),
                current_time,
                conversation_data.get('source', 'lmstudio'),
                conversation_data.get('input_tokens', 0),
                conversation_data.get('output_tokens', 0),
                conversation_data.get('reasoning_tokens', 0),
                conversation_data.get('cache_read_tokens', 0),
                conversation_data.get('tool_call_count', 0),
            ))
```

With:
```python
            cursor.execute('''
                INSERT INTO conversations (
                    filename, token_count, message_count, model,
                    created_at, user_last_message_at, updated_at,
                    source, input_tokens, output_tokens, reasoning_tokens, cache_read_tokens, cache_write_tokens, tool_call_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                filename,
                conversation_data.get('token_count', 0),
                conversation_data.get('message_count', 0),
                conversation_data.get('model', ''),
                conversation_data.get('created_at'),
                conversation_data.get('user_last_message_at', None),
                current_time,
                conversation_data.get('source', 'lmstudio'),
                conversation_data.get('input_tokens', 0),
                conversation_data.get('output_tokens', 0),
                conversation_data.get('reasoning_tokens', 0),
                conversation_data.get('cache_read_tokens', 0),
                conversation_data.get('cache_write_tokens', 0),
                conversation_data.get('tool_call_count', 0),
            ))
```

#### Step 1.6: Run tests to verify they pass

Run: `uv run pytest tests/test_schema_cache_write.py -v`
Expected: PASS — both tests pass with the new column present.

#### Step 1.7: Commit

```bash
git add lmstudio_db.py tests/test_schema_cache_write.py
git commit -m "feat: add cache_write_tokens column to conversations schema"
```

---

### Task 2: Create `pi_db.py` — Token Extraction Functions

**Files:**
- Create: `pi_db.py`
- Test: `tests/test_pi_db.py`

#### Step 2.1: Write failing tests for extraction functions

```python
"""Tests for pi database module."""
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import lmstudio_db


def test_extract_tokens_full():
    """Test extraction with all token types present."""
    usage = {
        "input": 1000,
        "output": 500,
        "cacheRead": 200,
        "cacheWrite": 300,
        "totalTokens": 2000,
    }
    inp, out, reason, cache_read, cache_write = _extract_tokens(usage)
    assert inp == 1000
    assert out == 500
    assert reason == 0
    assert cache_read == 200
    assert cache_write == 300


def test_extract_tokens_with_reasoning():
    """Test extraction with reasoning tokens."""
    usage = {
        "input": 100,
        "output": 200,
        "cacheRead": 50,
        "cacheWrite": 10,
        "totalTokens": 360,
    }
    # reasoning defaults to 0 for pi (pi usage has no 'reasoning' key)
    inp, out, reason, cache_read, cache_write = _extract_tokens(usage)
    assert inp == 100
    assert out == 200
    assert reason == 0
    assert cache_read == 50
    assert cache_write == 10


def test_extract_tokens_empty():
    """Test extraction with missing keys defaults to 0."""
    usage = {}
    inp, out, reason, cache_read, cache_write = _extract_tokens(usage)
    assert inp == 0 and out == 0 and reason == 0 and cache_read == 0 and cache_write == 0


def test_extract_tokens_zero_values():
    """Test extraction with explicit zero values."""
    usage = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
    inp, out, reason, cache_read, cache_write = _extract_tokens(usage)
    assert inp == 0 and out == 0 and reason == 0 and cache_read == 0 and cache_write == 0


def test_parse_timestamp_iso():
    """Test parsing ISO format timestamp string from pi JSONL."""
    result = _parse_timestamp("2026-06-06T15:36:15.145Z")
    assert isinstance(result, datetime)


def test_parse_timestamp_none():
    """Test parsing None returns None."""
    result = _parse_timestamp(None)
    assert result is None


def test_msg_to_conversation_valid():
    """Test converting a valid assistant message to conversation dict."""
    line = {
        "type": "message",
        "timestamp": "2026-06-06T15:36:15.145Z",
        "message": {
            "role": "assistant",
            "usage": {
                "input": 100,
                "output": 200,
                "cacheRead": 50,
                "cacheWrite": 10,
                "totalTokens": 360,
            },
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
    """Test that user messages are skipped."""
    line = {
        "type": "message",
        "timestamp": "2026-06-06T15:36:15.145Z",
        "message": {"role": "user", "content": "hello"},
    }
    result = _msg_to_conversation(line)
    assert result is None


def test_msg_to_conversation_skips_no_usage():
    """Test that messages without usage are skipped."""
    line = {
        "type": "message",
        "timestamp": "2026-06-06T15:36:15.145Z",
        "message": {"role": "assistant", "content": "hi"},
    }
    result = _msg_to_conversation(line)
    assert result is None


def test_msg_to_conversation_skips_non_message():
    """Test that non-message lines are skipped."""
    line = {"type": "model_change", "modelId": "gpt-4"}
    result = _msg_to_conversation(line)
    assert result is None


def test_msg_to_conversation_filename_format():
    """Test that filename uses timestamp-based unique name."""
    line = {
        "type": "message",
        "timestamp": "2026-06-06T15:36:15.145Z",
        "message": {
            "role": "assistant",
            "usage": {"input": 10, "output": 5, "cacheRead": 0, "cacheWrite": 0},
        },
    }
    result = _msg_to_conversation(line)
    assert result is not None
    # Filename should be derived from the timestamp
    assert "2026-06-06T15-36-15" in result["filename"] or result["filename"].startswith("pi_")


def test_msg_to_conversation_zero_tokens_skipped():
    """Test that assistant messages with zero total tokens are skipped."""
    line = {
        "type": "message",
        "timestamp": "2026-06-06T15:36:15.145Z",
        "message": {
            "role": "assistant",
            "usage": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        },
    }
    result = _msg_to_conversation(line)
    assert result is None


def test_msg_to_conversation_missing_message_key():
    """Test handling of line with no 'message' key."""
    line = {"type": "session", "id": "abc123"}
    result = _msg_to_conversation(line)
    assert result is None
```

#### Step 2.2: Run tests to verify they fail

Run: `uv run pytest tests/test_pi_db.py -v`
Expected: FAIL — `_extract_tokens`, `_parse_timestamp`, `_msg_to_conversation` are not defined.

#### Step 2.3: Write `pi_db.py` module

Create file `pi_db.py`:

```python
"""Pi session token usage extraction from JSONL session files.

Scans ~/.pi/agent/sessions/**/*.jsonl, extracts assistant messages with
usage data, and upserts into lmstudio_usage.db via lmstudio_db.upsert_conversation().
Mirrors the opencode_db.py pattern.
"""
import glob
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _extract_tokens(usage):
    """Extract token counts from a pi message usage dict.

    Args:
        usage: Dict with keys input, output, cacheRead, cacheWrite (and optional totalTokens).

    Returns:
        Tuple of (input_tokens, output_tokens, reasoning_tokens, cache_read_tokens, cache_write_tokens).
    """
    if not isinstance(usage, dict):
        return 0, 0, 0, 0, 0

    input_tok = int(usage.get("input", 0) or 0)
    output_tok = int(usage.get("output", 0) or 0)
    # Pi usage does not have a 'reasoning' key; default to 0
    reasoning_tok = 0
    cache_read_tok = int(usage.get("cacheRead", 0) or 0)
    cache_write_tok = int(usage.get("cacheWrite", 0) or 0)
    return input_tok, output_tok, reasoning_tok, cache_read_tok, cache_write_tok


def _parse_timestamp(ts_str):
    """Parse an ISO-format timestamp string to naive UTC datetime.

    Args:
        ts_str: ISO format timestamp string (e.g. '2026-06-06T15:36:15.145Z').

    Returns:
        datetime object (naive, UTC), or None on failure.
    """
    if not ts_str:
        return None
    try:
        # Handle Z suffix and fractional seconds
        ts_str = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_str)
        # Convert to naive UTC
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def _msg_to_conversation(line):
    """Convert a pi JSONL message line to a conversation dict for upsert.

    Args:
        line: Parsed JSON dict from a JSONL line.

    Returns:
        Dict compatible with lmstudio_db.upsert_conversation(), or None if
        the message should be skipped (not assistant, no usage, zero tokens).
    """
    if not isinstance(line, dict):
        return None

    # Only process message-type lines
    if line.get("type") != "message":
        return None

    message = line.get("message", {})
    if not isinstance(message, dict):
        return None

    # Only assistant messages
    if message.get("role") != "assistant":
        return None

    # Must have usage data
    usage = message.get("usage")
    if not usage or not isinstance(usage, dict):
        return None

    # Extract tokens
    input_tok, output_tok, reasoning_tok, cache_read_tok, cache_write_tok = _extract_tokens(usage)
    total_tokens = input_tok + output_tok + reasoning_tok + cache_read_tok + cache_write_tok

    # Skip zero-token messages
    if total_tokens == 0:
        return None

    # Use timestamp as created_at and filename for uniqueness
    ts_str = line.get("timestamp")
    created_at = _parse_timestamp(ts_str)

    # Generate a unique filename from timestamp + message id
    msg_id = message.get("id", "")
    if ts_str:
        # Convert ISO timestamp to safe filename format
        safe_ts = ts_str.replace(":", "-").replace(".", "_")
        filename = f"pi_{safe_ts}_{msg_id}"
    else:
        filename = f"pi_unknown_{msg_id}"

    return {
        "filename": filename,
        "token_count": total_tokens,
        "message_count": 1,
        "model": message.get("modelId", "") or "",
        "created_at": created_at,
        "user_last_message_at": created_at,
        "source": "pi",
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "reasoning_tokens": reasoning_tok,
        "cache_read_tokens": cache_read_tok,
        "cache_write_tokens": cache_write_tok,
        "tool_call_count": 0,
    }


def sync_pi_tokens(db_path: str | None = None, lmstudio_db_path: str | None = None) -> int:
    """Read assistant messages from pi JSONL session files and upsert into lmstudio_usage.db.

    Scans ~/.pi/agent/sessions/**/*.jsonl, extracts assistant messages with usage data,
    and writes each as a row in lmstudio_usage.db.conversations via upsert_conversation().

    Args:
        db_path: Base path to pi sessions directory. Defaults to ~/.pi/agent/sessions/.
        lmstudio_db_path: Path to lmstudio_usage.db. Defaults to data/lmstudio_usage.db.

    Returns:
        Number of conversations successfully synced.
    """
    from lmstudio_db import init_db, upsert_conversation

    if db_path is None:
        db_path = str(Path.home() / ".pi" / "agent" / "sessions")

    if lmstudio_db_path is None:
        lmstudio_db_path = str(Path(__file__).parent / "data" / "lmstudio_usage.db")

    # Check if sessions directory exists
    if not Path(db_path).exists():
        logger.warning(f"Pi sessions directory not found at {db_path}, skipping sync")
        return 0

    init_db(lmstudio_db_path)

    synced = 0
    skipped = 0

    # Find all JSONL files recursively
    jsonl_files = sorted(glob.glob(str(Path(db_path) / "**" / "*.jsonl"), recursive=True))

    for jsonl_file in jsonl_files:
        try:
            with open(jsonl_file, "r") as f:
                for line_num, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed = __import__("json").loads(line)
                    except __import__("json").JSONDecodeError:
                        skipped += 1
                        continue

                    conv = _msg_to_conversation(parsed)
                    if conv is None:
                        skipped += 1
                        continue

                    try:
                        upsert_conversation(lmstudio_db_path, conv)
                        synced += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to upsert message in {jsonl_file}:{line_num}: {e}"
                        )
                        skipped += 1

        except (OSError, IOError) as e:
            logger.warning(f"Could not read JSONL file {jsonl_file}: {e}")
            continue

    if skipped > 0:
        logger.info(f"Synced {synced} pi messages, skipped {skipped}")
    else:
        logger.info(f"Synced {synced} pi messages")

    return synced
```

#### Step 2.4: Run tests to verify they pass

Run: `uv run pytest tests/test_pi_db.py -v`
Expected: PASS — all extraction and conversion tests pass.

#### Step 2.5: Commit

```bash
git add pi_db.py tests/test_pi_db.py
git commit -m "feat: add pi_db module for scanning pi session JSONL files"
```

---

### Task 3: Add Integration Test for `sync_pi_tokens()`

**Files:**
- Modify: `tests/test_pi_db.py` (append)

#### Step 3.1: Write integration test that creates mock JSONL files and verifies DB output

Append to `tests/test_pi_db.py`:

```python
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

    synced = __import__("pi_db").sync_pi_tokens(
        db_path=os.path.join(tmpdir, "sessions"),
        lmstudio_db_path=lmstudio_db_path,
    )

    assert synced == 2  # msg_001 and msg_002 (user and zero-token skipped)

    # Verify data in DB
    conn = __import__("sqlite3").connect(lmstudio_db_path)
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
    assert row[4] == 0  # cache_write_tokens

    conn.close()


def test_sync_pi_tokens_no_sessions_dir():
    """Test graceful handling when sessions directory doesn't exist."""
    synced = __import__("pi_db").sync_pi_tokens(
        db_path="/nonexistent/pi/sessions"
    )
    assert synced == 0
```

#### Step 3.2: Run tests to verify they pass

Run: `uv run pytest tests/test_pi_db.py::test_sync_pi_tokens_basic -v`
Expected: PASS.

Run: `uv run pytest tests/test_pi_db.py::test_sync_pi_tokens_no_sessions_dir -v`
Expected: PASS.

#### Step 3.3: Commit

```bash
git add tests/test_pi_db.py
git commit -m "test: add integration tests for pi_db sync function"
```

---

### Task 4: Update `app.py` to Include Pi Sync Step

**Files:**
- Modify: `app.py` (lines ~18-47)

#### Step 4.1: Add pi sync step to `_load_all_sources()`

Insert after the OpenCode sync block (after line ~39, before "# 3. Load unified data from DB"):

```python
    # 3. Sync Pi sessions from JSONL files
    try:
        import pi_db
        pi_db.sync_pi_tokens()
    except Exception:
        pass  # Skip Pi sync if sessions directory doesn't exist

    # 4. Load unified data from DB
```

Also update the comment numbering for the load step from "3." to "4." in the existing code.

#### Step 4.2: Run full test suite to verify nothing breaks

Run: `uv run pytest -v`
Expected: All existing tests pass. The new pi_db.py module is imported at module level in app.py, but since it's inside a try/except, missing sessions won't cause failures.

#### Step 4.3: Commit

```bash
git add app.py
git commit -m "feat: add pi token sync to app startup"
```

---

### Task 5: Run Full Test Suite and Verify End-to-End

**Files:**
- All test files

#### Step 5.1: Run all tests

Run: `uv run pytest -v`
Expected: All tests pass including new pi_db tests and existing lmstudio/opencode tests.

#### Step 5.2: Commit (if any final tweaks)

```bash
git add -A
git commit -m "test: verify full test suite passes with pi integration"
```
