# OpenCode DB Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate OpenCode token data from JSON file scanning to direct SQLite queries against opencode.db, deleting the old module and updating app.py.

**Architecture:** Create `opencode_db.py` that queries opencode.db's `message` table using SQL with `json_extract()` to filter assistant messages with non-zero tokens, then upserts each row into lmstudio_usage.db via the existing `lmstudio_db.upsert_conversation()`. Delete `opencode_tokens.py` and its tests. Update `app.py` to use the new module.

**Tech Stack:** Python 3.12, sqlite3 (stdlib), pytest for testing.

---

### Task 1: Create opencode_db.py with sync_opencode_tokens function

**Files:**
- Create: `opencode_db.py`

```python
"""OpenCode token usage data extraction from opencode.db.

Queries ~/.local/share/opencode/opencode.db directly instead of
scanning JSON files (opencode_tokens.py). Upserts into lmstudio_usage.db
via lmstudio_db.upsert_conversation().
"""
import json
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_timestamp_ms(ms_value):
    """Convert millisecond timestamp to naive datetime (UTC).

    Args:
        ms_value: Integer or float timestamp in milliseconds.

    Returns:
        datetime object (naive, UTC), or None on failure.
    """
    if ms_value is None:
        return None
    try:
        ts = int(ms_value)
        if ts > 3999999999:
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).replace(tzinfo=None)
        else:
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
    except (ValueError, OSError, OverflowError):
        return None


def _extract_tokens(data_json):
    """Extract token counts from a message data JSON dict.

    Args:
        data_json: Parsed JSON dict from the 'data' column.

    Returns:
        Tuple of (input_tokens, output_tokens, reasoning_tokens, cache_read_tokens).
    """
    tokens = data_json.get("tokens", {}) if isinstance(data_json.get("tokens"), dict) else {}
    input_tok = int(tokens.get("input", 0) or 0)
    output_tok = int(tokens.get("output", 0) or 0)
    reasoning_tok = int(tokens.get("reasoning", 0) or 0)
    cache_obj = tokens.get("cache", {}) if isinstance(tokens.get("cache"), dict) else {}
    cache_read_tok = int(cache_obj.get("read", 0) or 0)
    return input_tok, output_tok, reasoning_tok, cache_read_tok


def _row_to_conversation(row):
    """Convert an opencode.db message row to a conversation dict for upsert.

    Args:
        row: Tuple (id, time_created, data_text) from the SQL query.

    Returns:
        Dict compatible with lmstudio_db.upsert_conversation(), or None if
        the message should be skipped (no model, zero tokens).
    """
    msg_id, time_created_ms, data_text = row

    try:
        data_json = json.loads(data_text) if isinstance(data_text, str) else None
    except (json.JSONDecodeError, TypeError):
        data_json = None

    if data_json is None:
        logger.warning(f"Skipping message {msg_id}: malformed JSON in data column")
        return None

    role = data_json.get("role", "")
    if role != "assistant":
        return None

    # Extract model — assistant messages have top-level modelID
    model_name = data_json.get("modelID") or ""
    if not model_name:
        logger.warning(f"Skipping message {msg_id}: no modelID found")
        return None

    # Extract tokens
    input_tok, output_tok, reasoning_tok, cache_read_tok = _extract_tokens(data_json)
    total_tokens = input_tok + output_tok + reasoning_tok + cache_read_tok

    if total_tokens == 0:
        return None

    created_at = _parse_timestamp_ms(time_created_ms)

    return {
        "filename": msg_id,
        "token_count": total_tokens,
        "message_count": 1,
        "model": model_name,
        "created_at": created_at,
        "user_last_message_at": created_at,
        "source": "opencode",
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "reasoning_tokens": reasoning_tok,
        "cache_read_tokens": cache_read_tok,
    }


def sync_opencode_tokens(db_path: str | None = None) -> int:
    """Read assistant messages from opencode.db and upsert into lmstudio_usage.db.

    Queries the message table for assistant messages with non-zero token counts,
    extracts model/token data from the JSON 'data' column, and writes each
    message as a row in lmstudio_usage.db.conversations via upsert_conversation().

    Args:
        db_path: Path to opencode.db. Defaults to ~/.local/share/opencode/opencode.db.

    Returns:
        Number of conversations successfully synced.
    """
    from lmstudio_db import init_db, upsert_conversation

    if db_path is None:
        db_path = str(Path.home() / ".local" / "share" / "opencode" / "opencode.db")

    # Check if opencode.db exists
    if not Path(db_path).exists():
        logger.warning(f"opencode.db not found at {db_path}, skipping sync")
        return 0

    # SQL query: filter assistant messages with non-zero tokens
    query = """
        SELECT id, time_created, data
        FROM message
        WHERE json_extract(data, '$.role') = 'assistant'
          AND (COALESCE(json_extract(data, '$.tokens.input'), 0)
             + COALESCE(json_extract(data, '$.tokens.output'), 0)
             + COALESCE(json_extract(data, '$.tokens.reasoning'), 0)
             + COALESCE(json_extract(data, '$.tokens.cache.read'), 0)) > 0
    """

    lmstudio_db_path = str(Path(__file__).parent / "data" / "lmstudio_usage.db")
    init_db(lmstudio_db_path)

    synced = 0
    skipped = 0

    try:
        conn = sqlite3.connect(db_path, uri=True, mode="ro")
        conn.row_factory = None
    except sqlite3.Error as e:
        logger.warning(f"Could not open opencode.db at {db_path}: {e}")
        return 0

    cursor = conn.cursor()
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logger.warning(f"Query failed on opencode.db: {e}")
        conn.close()
        return 0

    for row in rows:
        conv = _row_to_conversation(row)
        if conv is None:
            skipped += 1
            continue
        try:
            upsert_conversation(lmstudio_db_path, conv)
            synced += 1
        except Exception as e:
            logger.warning(f"Failed to upsert message {row[0]}: {e}")
            skipped += 1

    conn.close()
    if skipped > 0:
        logger.info(f"Synced {synced} opencode messages, skipped {skipped}")
    else:
        logger.info(f"Synced {synced} opencode messages")

    return synced
```

- [ ] **Step 1: Write opencode_db.py** — Create the file with all functions above.

- [ ] **Step 2: Verify it imports without errors**

Run: `uv run python -c "import opencode_db; print('Import OK')"`
Expected: `Import OK` (no errors)

---

### Task 2: Create tests/test_opencode_db.py

**Files:**
- Create: `tests/test_opencode_db.py`

```python
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

    with patch.object(opencode_db.Path, 'home') as mock_home:
        mock_home.return_value = Path(tmpdir)
        # Override the default db path by passing explicitly
        synced = opencode_db.sync_opencode_tokens(
            db_path=os.path.join(tmpdir, "opencode_test.db")
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
        db_path=opencode_db_path
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
    synced1 = opencode_db.sync_opencode_tokens(db_path=opencode_db_path)
    assert synced1 == 2

    # Second sync (should not duplicate)
    synced2 = opencode_db.sync_opencode_tokens(db_path=opencode_db_path)
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
```

- [ ] **Step 1: Write tests/test_opencode_db.py** — Create the test file with all tests above.

- [ ] **Step 2: Run new tests to verify they pass**

Run: `uv run pytest tests/test_opencode_db.py -v`
Expected: All 9 tests PASS

---

### Task 3: Update app.py to use opencode_db instead of opencode_tokens

**Files:**
- Modify: `app.py:15-36` (the `_load_all_sources` function)

Replace the entire `_load_all_sources` function with:

```python
def _load_all_sources():
    """Scan LMStudio conversations and sync OpenCode tokens, then load unified data."""
    from pathlib import Path
    
    # 1. Scan and upsert LMStudio conversations (unchanged)
    from lmstudio_tokens import scan_conversations as ls_scan, load_conversations_from_files as ls_load
    from lmstudio_db import init_db, upsert_conversation

    json_files = ls_scan()
    if json_files:
        conversations = ls_load(json_files)
        init_db(str(_DB_PATH))
        for conv in conversations:
            conv.setdefault('source', 'lmstudio')
            upsert_conversation(str(_DB_PATH), conv)

    # 2. Sync OpenCode messages from opencode.db (NEW — replaces opencode_tokens)
    import opencode_db
    opencode_db.sync_opencode_tokens()

    # 3. Load unified data from DB
    from data_loader import load_unified_data
    try:
        df = load_unified_data(str(_DB_PATH))
        return df if not df.empty else None
    except Exception:
        return None
```

- [ ] **Step 1: Edit app.py** — Replace lines 15-36 with the new `_load_all_sources` function above. Remove `from opencode_tokens import ...` and replace with `import opencode_db; opencode_db.sync_opencode_tokens()`.

- [ ] **Step 2: Verify app.py imports without errors**

Run: `uv run python -c "import app; print('App import OK')"`
Expected: `App import OK` (may show warnings about missing DB files, but no ImportError)

---

### Task 4: Delete opencode_tokens.py and its tests

**Files:**
- Delete: `opencode_tokens.py`
- Delete: `tests/test_opencode_tokens.py`

- [ ] **Step 1: Delete opencode_tokens.py**

Run: `rm opencode_tokens.py`

- [ ] **Step 2: Delete tests/test_opencode_tokens.py**

Run: `rm tests/test_opencode_tokens.py`

---

### Task 5: Run full test suite to verify everything works

**Files:**
- All existing tests (except test_opencode_tokens.py which is deleted)

- [ ] **Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All remaining tests PASS (test_database, test_extraction, test_loader, test_unified_loader, test_opencode_db)

- [ ] **Step 2: Verify no references to opencode_tokens remain in the codebase**

Run: `grep -r "opencode_tokens" --include="*.py" .`
Expected: No results (except possibly in git history)

---

### Task 6: Commit all changes

- [ ] **Step 1: Stage and commit**

```bash
git add opencode_db.py tests/test_opencode_db.py app.py
git rm opencode_tokens.py tests/test_opencode_tokens.py
git commit -m "feat: migrate OpenCode token extraction from JSON files to opencode.db"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Delete opencode_tokens.py → Task 4
- ✅ Delete tests/test_opencode_tokens.py → Task 4
- ✅ Create opencode_db.py with sync function → Task 1
- ✅ Query opencode.db message table for assistant messages with non-zero tokens → Task 1 (SQL query in `sync_opencode_tokens`)
- ✅ Extract model/token data from JSON data column using json_extract() → Task 1 (SQL uses `json_extract(data, '$.role')`, etc.)
- ✅ Upsert into lmstudio_usage.db via upsert_conversation() → Task 1
- ✅ Each message becomes one row keyed by message.id, source='opencode' → Task 1 (`_row_to_conversation`)
- ✅ Update app.py → Task 3
- ✅ Error handling (missing db, malformed JSON, upsert failures) → Task 1 (logger warnings, graceful returns)
- ✅ Tests for opencode_db → Task 2

**2. Placeholder scan:** No "TBD", "TODO", or vague references found. All code is complete in every step.

**3. Type consistency:** All function signatures match between opencode_db.py and app.py usage. The `_row_to_conversation` return dict matches the fields expected by `lmstudio_db.upsert_conversation()`.

**4. Edge cases covered in tests:**
- ✅ Assistant messages with tokens → synced
- ✅ Assistant messages with zero tokens → filtered out
- ✅ User messages → filtered out
- ✅ Missing opencode.db → returns 0 gracefully
- ✅ Malformed JSON data → skipped with warning
- ✅ Messages without modelID → skipped
- ✅ Re-sync (idempotency) → no duplicates
- ✅ Reasoning and cache tokens extracted correctly
