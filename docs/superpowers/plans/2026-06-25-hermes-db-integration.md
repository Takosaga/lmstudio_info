# Hermes DB Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Hermes Agent session data to the lmstudio_info dashboard by syncing from `~/.hermes/state.db` SQLite database.

**Architecture:** Read aggregated token counts directly from the `sessions` table (one row per session), normalize model names, convert timestamps, and upsert into the existing conversations table via `lmstudio_db.upsert_conversation()`. No per-message parsing needed — Hermes stores pre-aggregated data.

**Tech Stack:** Python 3.12+, SQLite (stdlib), pytest, pandas, plotly, shiny.

## Global Constraints

- Follow exact patterns from `opencode_db.py` and `pi_db.py` — same function signatures, same error handling, same import structure
- Model name normalization: strip provider prefixes via `re.sub(r"^[a-zA-Z][a-zA-Z0-9_-]+/", "", model)` (identical regex used in all three sync functions)
- Source column always set to `'hermes'`
- Timestamps stored as naive UTC datetimes in conversations table
- If `~/.hermes/state.db` doesn't exist or can't be opened, silently return 0 (no exceptions propagate)
- All tests use temporary directories and isolated DB instances — never touch real `~/.hermes/state.db`

---

### Task 1: Create hermes_db.py with sync_hermes_tokens()

**Files:**
- Create: `hermes_db.py`

**Interfaces:**
- Consumes: `lmstudio_db.init_db()`, `lmstudio_db.upsert_conversation()`
- Produces: `sync_hermes_tokens(db_path=None, lmstudio_db_path=None)` → `int` (count of synced sessions)

- [ ] **Step 1: Write hermes_db.py**

Create `hermes_db.py` with the following complete content:

```python
"""Hermes Agent session token usage extraction from state.db.

Reads aggregated session data from ~/.hermes/state.db SQLite database and
upserts into lmstudio_usage.db via lmstudio_db.upsert_conversation().
Mirrors the opencode_db.py / pi_db.py pattern.
"""
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_timestamp(ts_value):
    """Convert a Unix timestamp (REAL float) to naive datetime (UTC).

    Args:
        ts_value: Unix timestamp as int or float.

    Returns:
        datetime object (naive, UTC), or None on failure.
    """
    if ts_value is None:
        return None
    try:
        dt = datetime.fromtimestamp(ts_value, tz=timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError, OSError, OverflowError):
        return None


def _row_to_conversation(row):
    """Convert a sessions table row to a conversation dict for upsert.

    Args:
        row: Tuple from SQLite cursor — (id, source, user_id, model, model_config,
             system_prompt, parent_session_id, started_at, ended_at, end_reason,
             message_count, tool_call_count, input_tokens, output_tokens,
             cache_read_tokens, cache_write_tokens, reasoning_tokens,
             billing_provider, billing_base_url, billing_mode, estimated_cost_usd,
             actual_cost_usd, cost_status, cost_source, pricing_version, title,
             api_call_count, handoff_state, handoff_platform, handoff_error,
             rewind_count, archived).

    Returns:
        Dict compatible with lmstudio_db.upsert_conversation(), or None if
        the session should be skipped (no model, zero tokens).
    """
    try:
        sid = row[0]           # id
        _source = row[1]       # source (cli, signal, telegram, etc.)
        _user_id = row[2]      # user_id
        model_name = row[3]    # model
        _model_config = row[4]  # model_config
        _system_prompt = row[5]  # system_prompt
        _parent_session_id = row[6]  # parent_session_id
        started_at = row[7]    # started_at (REAL unix timestamp)
        ended_at = row[8]      # ended_at (REAL unix timestamp)
        _end_reason = row[9]   # end_reason
        message_count = row[10]  # message_count
        tool_call_count = row[11]  # tool_call_count
        input_tokens = int(row[12] or 0)  # input_tokens
        output_tokens = int(row[13] or 0)  # output_tokens
        cache_read_tokens = int(row[14] or 0)  # cache_read_tokens
        cache_write_tokens = int(row[15] or 0)  # cache_write_tokens
        reasoning_tokens = int(row[16] or 0)  # reasoning_tokens
    except (IndexError, TypeError):
        return None

    if not model_name:
        return None

    total_tokens = input_tokens + output_tokens + reasoning_tokens + cache_read_tokens + cache_write_tokens

    if total_tokens == 0:
        return None

    # Normalize model name — strip provider/community prefix for cross-source merging
    model_name = re.sub(r"^[a-zA-Z][a-zA-Z0-9_-]+/", "", model_name)

    created_at = _parse_timestamp(started_at)
    user_last_message_at = _parse_timestamp(ended_at)

    # Session ID is the unique primary key — use directly as filename
    return {
        "filename": sid,
        "token_count": total_tokens,
        "message_count": int(message_count or 0),
        "model": model_name,
        "created_at": created_at,
        "user_last_message_at": user_last_message_at,
        "source": "hermes",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "tool_call_count": int(tool_call_count or 0),
    }


def sync_hermes_tokens(db_path=None, lmstudio_db_path=None):
    """Read sessions from Hermes state.db and upsert into lmstudio_usage.db.

    Reads aggregated token counts directly from the sessions table — no
    per-message parsing needed since Hermes stores pre-aggregated data.

    Args:
        db_path: Path to ~/.hermes/state.db. Defaults to auto-detection.
        lmstudio_db_path: Path to lmstudio_usage.db. Defaults to data/lmstudio_usage.db.

    Returns:
        Number of conversations successfully synced.
    """
    from lmstudio_db import init_db, upsert_conversation

    if db_path is None:
        db_path = str(Path.home() / ".hermes" / "state.db")

    if lmstudio_db_path is None:
        lmstudio_db_path = str(Path(__file__).parent / "data" / "lmstudio_usage.db")

    if not Path(db_path).exists():
        logger.warning(f"Hermes state.db not found at {db_path}, skipping sync")
        return 0

    init_db(lmstudio_db_path)

    synced = 0

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT id, source, user_id, model, model_config, system_prompt,
                   parent_session_id, started_at, ended_at, end_reason,
                   message_count, tool_call_count, input_tokens, output_tokens,
                   cache_read_tokens, cache_write_tokens, reasoning_tokens,
                   billing_provider, billing_base_url, billing_mode,
                   estimated_cost_usd, actual_cost_usd, cost_status,
                   cost_source, pricing_version, title, api_call_count,
                   handoff_state, handoff_platform, handoff_error,
                   rewind_count, archived
            FROM sessions
        """)

        for row in c.fetchall():
            conv = _row_to_conversation(row)
            if conv is None:
                continue
            try:
                upsert_conversation(lmstudio_db_path, conv)
                synced += 1
            except Exception as e:
                logger.warning(f"Failed to upsert session {row['id']}: {e}")

        conn.close()
    except Exception as e:
        logger.warning(f"Could not open Hermes state.db at {db_path}: {e}")
        return 0

    logger.info(f"Synced {synced} hermes sessions")
    return synced
```

- [ ] **Step 2: Verify syntax**

Run: `uv run python -c "import hermes_db; print('OK')"`
Expected: `OK` (module imports without error)

---

### Task 2: Create tests for hermes_db.py

**Files:**
- Test: `tests/test_hermes_db.py`

**Interfaces:**
- Consumes: `hermes_db.sync_hermes_tokens()`, `hermes_db._row_to_conversation()`, `hermes_db._parse_timestamp()`, `lmstudio_db.init_db()`
- Produces: 8+ test functions covering extraction, conversion, full sync, and error handling

- [ ] **Step 1: Write tests**

Create `tests/test_hermes_db.py` with the following complete content:

```python
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

    # Session with all token types
    c.execute("""
        INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "20260624_194845_f20214", "cli", None, "qwen3.5-9b-mtp@q4_k_xl",
        json.dumps({"max_iterations": 150}), "SOUL.md content...", None,
        1782319725.726, 1782320109.798, "cli_close",
        32, 14, 316542, 2067, 0, 0, 0,
        "lmstudio", "http://127.0.0.1:1234/v1", None,
        0.0, None, "unknown", "none", None,
        "Where Hermes Stores Session Data", 16, None, None, None, 0, 0
    ))

    # Session with reasoning tokens
    c.execute("""
        INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "20260625_100000_aabb11", "cli", None, "test-reasoning-model",
        None, None, None,
        1782400000.0, 1782401000.0, "timeout",
        10, 5, 1000, 500, 0, 0, 200,
        None, None, None,
        None, None, None, None, None,
        "Test reasoning session", 5, None, None, None, 0, 0
    ))

    # Session with cache tokens
    c.execute("""
        INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "20260625_110000_ccdd22", "signal", None, "lmstudio-community/qwen-7b",
        None, None, None,
        1782403600.0, 1782404000.0, "cli_close",
        5, 2, 500, 300, 10000, 500, 0,
        None, None, None,
        None, None, None, None, None,
        "Signal chat with cache", 3, None, None, None, 0, 0
    ))

    # Session with zero tokens (should be filtered)
    c.execute("""
        INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "20260625_120000_eeff33", "cli", None, "empty-model",
        None, None, None,
        1782407200.0, 1782407210.0, "empty",
        0, 0, 0, 0, 0, 0, 0,
        None, None, None,
        None, None, None, None, None,
        "Empty session", 0, None, None, None, 0, 0
    ))

    # Session with no model (should be filtered)
    c.execute("""
        INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "20260625_130000_gg4444", "telegram", None, None,
        None, None, None,
        1782410800.0, 1782411000.0, "cli_close",
        2, 0, 10, 5, 0, 0, 0,
        None, None, None,
        None, None, None, None, None,
        "No model session", 1, None, None, None, 0, 0
    ))

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
```

- [ ] **Step 2: Run all tests**

Run: `uv run pytest tests/test_hermes_db.py -v`
Expected: All 13 tests PASS

---

### Task 3: Wire hermes into app.py _load_all_sources()

**Files:**
- Modify: `app.py` — add third sync call in `_load_all_sources()`

**Interfaces:**
- Consumes: `hermes_db.sync_hermes_tokens()` (from Task 1)
- Produces: Herme sessions appear in dashboard alongside LMStudio, OpenCode, and Pi data

- [ ] **Step 1: Add hermes sync to app.py**

In `_load_all_sources()`, after the Pi sync block (around line 47), add:

```python
    # 4. Sync Hermes sessions from state.db
    try:
        import hermes_db
        hermes_db.sync_hermes_tokens()
    except Exception:
        pass  # Skip Hermes sync if path doesn't exist
```

The function should read lines ~44-50 in app.py and add the new block after the Pi sync. The complete `_load_all_sources()` should have exactly four source blocks (LMStudio, OpenCode, Pi, Hermes), each wrapped in its own try/except.

- [ ] **Step 2: Verify dashboard loads**

Run: `uv run python -c "from app import _load_all_sources; _load_all_sources(); print('OK')"`
Expected: `OK` (no errors during sync)

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest`
Expected: All existing tests PASS + 13 new hermes tests PASS (total should increase by 13)

---

## Self-Review Checklist

1. **Spec coverage:** All spec requirements covered — session-level aggregates only, filename = session ID, source = 'hermes', model normalization, timestamp conversion, error handling, file list matches spec exactly.
2. **Placeholder scan:** No TBD/TODO/fill-in placeholders. Every code block is complete. Every test has assertions.
3. **Type consistency:** `_row_to_conversation()` takes a SQLite row tuple and returns a dict matching `lmstudio_db.upsert_conversation()` signature (filename, token_count, message_count, model, created_at, user_last_message_at, source, input_tokens, output_tokens, reasoning_tokens, cache_read_tokens, cache_write_tokens, tool_call_count). All three sync functions use identical return dict structure.
4. **Error handling:** Missing DB → returns 0 silently. Bad rows → `_row_to_conversation` returns None. SQLite open failure → catches exception and returns 0. Matches opencode_db.py pattern (read-only URI mode).
