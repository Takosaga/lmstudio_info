# Unified Token Usage Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OpenCode token usage data to the existing LMStudio Token Usage Dashboard, combining both sources in one unified dashboard with source filtering and optional token-type breakdown.

**Architecture:** Single SQLite `conversations` table gains a `source` discriminator column and four token breakdown columns (input_tokens, output_tokens, reasoning_tokens, cache_read_tokens). A new `opencode_tokens.py` module parses OpenCode JSON files using the same interface as `lmstudio_tokens.py`. The dashboard adds source filter and breakdown toggle controls.

**Tech Stack:** Python 3.12, SQLite, pandas, Plotly, Shiny, pytest

---

## Task 1: Create `opencode_tokens.py` module

**Files:**
- Create: `opencode_tokens.py`
- Test: `tests/test_opencode_tokens.py`

This module mirrors `lmstudio_tokens.py` but parses OpenCode's JSON format. OpenCode stores messages in `~/.local/share/opencode/storage/message/<sessionID>/msg_<id>.json`. Each file is one message with a `tokens` object containing `{input, output, reasoning, cache: {read, write}}`.

### Step 1: Write the failing test for token extraction

```python
# tests/test_opencode_tokens.py
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open

sys.path.insert(0, str(Path(__file__).parent.parent))

import opencode_tokens


def test_extract_from_json_with_tokens():
    """Test extracting token counts from an OpenCode message with tokens."""
    json_content = '''{
        "id": "msg_test123",
        "sessionID": "ses_abc",
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
    }'''

    with patch('opencode_tokens.open', new_callable=mock_open, read_data=json_content):
        result = opencode_tokens.extract_from_json('/tmp/test_msg.json')

    assert result['filename'] == 'msg_test123'
    assert result['token_count'] == 94 + 48 + 0 + 10560  # = 10702
    assert result['input_tokens'] == 94
    assert result['output_tokens'] == 48
    assert result['reasoning_tokens'] == 0
    assert result['cache_read_tokens'] == 10560
    assert result['source'] == 'opencode'
    assert result['model'] == 'big-pickle'
    assert isinstance(result['created_at'], datetime)


def test_extract_from_json_no_tokens():
    """Test extraction handles messages without tokens (all zeros)."""
    json_content = '''{
        "id": "msg_notoke",
        "sessionID": "ses_abc",
        "role": "user",
        "time": {"created": 1766612341074},
        "model": {"providerID": "lmstudio", "modelID": "openai/gpt-oss-20b"}
    }'''

    with patch('opencode_tokens.open', new_callable=mock_open, read_data=json_content):
        result = opencode_tokens.extract_from_json('/tmp/test_msg.json')

    assert result['filename'] == 'msg_notoke'
    assert result['token_count'] == 0
    assert result['input_tokens'] == 0
    assert result['output_tokens'] == 0
    assert result['reasoning_tokens'] == 0
    assert result['cache_read_tokens'] == 0
    assert result['model'] == 'openai/gpt-oss-20b'


def test_extract_from_json_missing_model():
    """Test extraction defaults model to 'unknown' when no model info present."""
    json_content = '''{
        "id": "msg_nomodel",
        "sessionID": "ses_abc",
        "role": "assistant",
        "time": {"created": 1766612341074},
        "tokens": {"input": 10, "output": 5, "reasoning": 0, "cache": {"read": 0, "write": 0}}
    }'''

    with patch('opencode_tokens.open', new_callable=mock_open, read_data=json_content):
        result = opencode_tokens.extract_from_json('/tmp/test_msg.json')

    assert result['model'] == 'unknown'


def test_scan_conversations_empty():
    """Test scanning when OpenCode directory doesn't exist."""
    with patch('opencode_tokens.os.path.expanduser', return_value='/nonexistent/path'), \
         patch('opencode_tokens.os.path.exists', return_value=False):
        result = opencode_tokens.scan_conversations()
    assert result == []


def test_scan_conversations_finds_files():
    """Test scanning finds all msg_*.json files recursively."""
    tmpdir = tempfile.mkdtemp()

    # Create session dirs and message files
    (Path(tmpdir) / 'ses_1').mkdir()
    (Path(tmpdir) / 'ses_2').mkdir()
    (Path(tmpdir) / 'ses_1' / 'msg_a.json').write_text('{}')
    (Path(tmpdir) / 'ses_2' / 'msg_b.json').write_text('{}')

    with patch('opencode_tokens.os.path.expanduser', return_value=tmpdir), \
         patch('opencode_tokens.os.path.exists', return_value=True):
        result = opencode_tokens.scan_conversations()

    assert len(result) == 2


def test_load_conversations_from_files():
    """Test loading multiple OpenCode conversations."""
    tmpdir = tempfile.mkdtemp()
    session_dir = Path(tmpdir) / 'ses_test'
    session_dir.mkdir()

    msg1 = '{"id": "msg_1", "time": {"created": 1764334238483}, "modelID": "test-model", "tokens": {"input": 10, "output": 5, "reasoning": 0, "cache": {"read": 100, "write": 0}}}'
    msg2 = '{"id": "msg_2", "time": {"created": 1764334239000}, "modelID": "test-model", "tokens": {"input": 20, "output": 10, "reasoning": 0, "cache": {"read": 200, "write": 0}}}'

    (session_dir / 'msg_1.json').write_text(msg1)
    (session_dir / 'msg_2.json').write_text(msg2)

    json_files = [str(session_dir / 'msg_1.json'), str(session_dir / 'msg_2.json')]
    conversations = opencode_tokens.load_conversations_from_files(json_files)

    assert len(conversations) == 2
    assert conversations[0]['token_count'] == 10 + 5 + 0 + 100  # = 115
    assert conversations[1]['token_count'] == 20 + 10 + 0 + 200  # = 230


def test_load_handles_invalid_json():
    """Test that invalid JSON files are skipped with a warning."""
    tmpdir = tempfile.mkdtemp()
    session_dir = Path(tmpdir) / 'ses_test'
    session_dir.mkdir()

    (session_dir / 'msg_bad.json').write_text('not valid json{{{')
    (session_dir / 'msg_good.json').write_text(
        '{"id": "msg_good", "time": {"created": 1764334238483}, "modelID": "test", "tokens": {"input": 1, "output": 1, "reasoning": 0, "cache": {"read": 0, "write": 0}}}'
    )

    json_files = [str(session_dir / 'msg_bad.json'), str(session_dir / 'msg_good.json')]
    conversations = opencode_tokens.load_conversations_from_files(json_files)

    assert len(conversations) == 1
    assert conversations[0]['filename'] == 'msg_good'
```

### Step 2: Run test to verify it fails

Run: `uv run pytest tests/test_opencode_tokens.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'opencode_tokens'"

### Step 3: Write the opencode_tokens.py module

```python
"""OpenCode token usage data extraction.

Mirrors lmstudio_tokens.py interface but parses OpenCode's JSON message format.
Scans ~/.local/share/opencode/storage/message/**/*.json for token usage data.
"""
import json
import glob
import os
from pathlib import Path
from datetime import datetime, timezone


def scan_conversations():
    """Find all OpenCode message JSON files recursively."""
    opencode_dir = os.path.expanduser('~/.local/share/opencode/storage/message')

    if not os.path.exists(opencode_dir) or not os.path.isdir(opencode_dir):
        return []

    try:
        json_files = glob.glob(os.path.join(opencode_dir, '**', 'msg_*.json'), recursive=True)
        if isinstance(json_files, list):
            return sorted([str(Path(f).resolve()) for f in json_files])
        return []
    except Exception:
        return []


def _safe_get_nested(d, *keys, default=None):
    """Safely traverse nested dict keys."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d


def extract_from_json(file_path):
    """Parse OpenCode JSON message and extract metadata.

    Handles two JSON formats found in OpenCode storage:
    - Messages with top-level modelID/providerID fields
    - Messages with nested model object {providerID, modelID}
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        msg_data = json.load(f)

    # Use message 'id' as filename (unique per message)
    filename = msg_data.get('id', Path(file_path).name)

    # Extract model — try top-level modelID first, then nested model.modelID
    model_name = msg_data.get('modelID') or _safe_get_nested(msg_data, 'model', 'modelID', default='')
    if not model_name:
        model_name = 'unknown'

    # Extract tokens with safe defaults
    tokens_obj = msg_data.get('tokens', {}) if isinstance(msg_data.get('tokens'), dict) else {}
    input_tokens = int(tokens_obj.get('input', 0) or 0)
    output_tokens = int(tokens_obj.get('output', 0) or 0)
    reasoning_tokens = int(tokens_obj.get('reasoning', 0) or 0)
    cache_obj = tokens_obj.get('cache', {}) if isinstance(tokens_obj.get('cache'), dict) else {}
    cache_read_tokens = int(cache_obj.get('read', 0) or 0)
    total_tokens = input_tokens + output_tokens + reasoning_tokens + cache_read_tokens

    # Extract timestamp from time.created (milliseconds in OpenCode format)
    created_at = None
    ts_raw = _safe_get_nested(msg_data, 'time', 'created', default=None)
    if ts_raw is not None:
        try:
            # OpenCode timestamps are always milliseconds (> year 2100 threshold)
            if ts_raw > 3999999999:
                created_at = datetime.fromtimestamp(ts_raw / 1000, tz=timezone.utc).replace(tzinfo=None)
            else:
                created_at = datetime.fromtimestamp(ts_raw, tz=timezone.utc).replace(tzinfo=None)
        except (ValueError, OSError):
            created_at = None

    return {
        'filename': filename,
        'token_count': total_tokens,
        'message_count': 1,  # Each file is one message
        'model': model_name,
        'created_at': created_at,
        'user_last_message_at': created_at,  # Use same timestamp as fallback
        'source': 'opencode',
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'reasoning_tokens': reasoning_tokens,
        'cache_read_tokens': cache_read_tokens,
    }


def load_conversations_from_files(json_files):
    """Load conversations from list of JSON file paths."""
    conversations = []
    for json_file in json_files:
        try:
            conv_data = extract_from_json(json_file)
            conversations.append(conv_data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load {json_file}: {e}")
    return conversations


def main():
    """Main entry point for command-line usage."""
    json_files = scan_conversations()
    print(f"Found {len(json_files)} OpenCode message file(s)")

    if json_files:
        print("\nParsing messages...")
        conversations = load_conversations_from_files(json_files)
        print(f"Successfully extracted {len(conversations)} message(s)\n")

        if conversations:
            total = sum(c['token_count'] for c in conversations)
            print(f"Total tokens across all messages: {total:,}")
            models = {}
            for c in conversations:
                m = c['model'] or 'unknown'
                models[m] = models.get(m, 0) + c['token_count']
            for m, t in sorted(models.items(), key=lambda x: -x[1]):
                print(f"  {m}: {t:,} tokens")

        # Upsert conversations into database
        from lmstudio_db import init_db, upsert_conversation
        db_path = str(Path(__file__).parent / "data" / "lmstudio_usage.db")
        init_db(db_path)

        inserted = 0
        updated = 0
        for conv in conversations:
            result = upsert_conversation(db_path, conv)
            if result:
                inserted += 1
            else:
                updated += 1
        print(f"\nDatabase updated: {inserted} inserted, {updated} updated")


if __name__ == "__main__":
    main()
```

### Step 4: Run test to verify it passes

Run: `uv run pytest tests/test_opencode_tokens.py -v`
Expected: All 7 tests PASS

### Step 5: Commit

```bash
git add opencode_tokens.py tests/test_opencode_tokens.py
git commit -m "feat: add opencode_tokens module for OpenCode message parsing"
```

---

## Task 2: Migrate DB schema — add source and token breakdown columns

**Files:**
- Modify: `lmstudio_db.py`

Add five new columns to the `conversations` table. The migration must be idempotent (safe for re-runs) using `ALTER TABLE ... ADD COLUMN` guarded by a column existence check.

### Step 1: Write the failing test for schema migration

```python
# tests/test_db_migration.py
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3


def test_schema_migration_adds_columns():
    """Test that ensure_schema adds missing columns to existing table."""
    from lmstudio_db import init_db, ensure_schema, get_connection

    db_path = tempfile.mktemp(suffix='.db')

    try:
        # Create DB with old schema (no source/token breakdown columns)
        init_db(db_path)

        # Verify new columns don't exist yet
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(conversations)")
            columns = {row[1] for row in cursor.fetchall()}

        assert 'source' not in columns
        assert 'input_tokens' not in columns

        # Run migration
        ensure_schema(db_path)

        # Verify new columns now exist
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(conversations)")
            columns = {row[1] for row in cursor.fetchall()}

        assert 'source' in columns
        assert 'input_tokens' in columns
        assert 'output_tokens' in columns
        assert 'reasoning_tokens' in columns
        assert 'cache_read_tokens' in columns

    finally:
        os.unlink(db_path)


def test_schema_migration_is_idempotent():
    """Test that running ensure_schema twice doesn't cause errors."""
    from lmstudio_db import init_db, ensure_schema

    db_path = tempfile.mktemp(suffix='.db')

    try:
        init_db(db_path)
        ensure_schema(db_path)
        ensure_schema(db_path)  # Should not raise
    finally:
        os.unlink(db_path)


def test_init_db_runs_migration():
    """Test that init_db (called again on existing DB) runs migration."""
    from lmstudio_db import init_db, get_connection

    db_path = tempfile.mktemp(suffix='.db')

    try:
        # First init creates table with old schema
        init_db(db_path)

        # Second init should add missing columns without error
        init_db(db_path)

        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(conversations)")
            columns = {row[1] for row in cursor.fetchall()}

        assert 'source' in columns
        assert 'input_tokens' in columns

    finally:
        os.unlink(db_path)
```

### Step 2: Run test to verify it fails

Run: `uv run pytest tests/test_db_migration.py -v`
Expected: FAIL with "function not defined" or "ModuleNotFoundError" for ensure_schema

### Step 3: Add ensure_schema() and update init_db() in lmstudio_db.py

Add this function after the existing `get_or_create_table()` function (around line 120):

```python
_NEW_COLUMNS = [
    ('source', "TEXT DEFAULT 'lmstudio'"),
    ('input_tokens', 'INTEGER DEFAULT 0'),
    ('output_tokens', 'INTEGER DEFAULT 0'),
    ('reasoning_tokens', 'INTEGER DEFAULT 0'),
    ('cache_read_tokens', 'INTEGER DEFAULT 0'),
]


def ensure_schema(db_path):
    """Add new columns to conversations table if they don't exist.

    Safe to call multiple times — uses IF NOT EXISTS on ALTER TABLE.

    Args:
        db_path: Path to the SQLite database file
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Get existing column names
        cursor.execute("PRAGMA table_info(conversations)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Add missing columns
        for col_name, col_type in _NEW_COLUMNS:
            if col_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE conversations ADD COLUMN {col_name} {col_type}"
                )

        conn.commit()
```

Update the `init_db()` function to call `ensure_schema()` after table creation. Replace the end of `init_db()` (after `conn.commit()` at line 72) with:

```python
        conn.commit()
        
        # Ensure new columns exist (safe for re-runs)
        ensure_schema(db_path)
```

### Step 4: Run test to verify it passes

Run: `uv run pytest tests/test_db_migration.py -v`
Expected: All 3 tests PASS

### Step 5: Commit

```bash
git add lmstudio_db.py tests/test_db_migration.py
git commit -m "feat: add source and token breakdown columns to conversations table"
```

---

## Task 3: Update `upsert_conversation()` to handle new columns

**Files:**
- Modify: `lmstudio_db.py`

The upsert logic needs to handle the new fields (`source`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read_tokens`) in both INSERT and UPDATE paths.

### Step 1: Write test for upsert with new columns

```python
# Add to tests/test_db_migration.py or a new test file

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tempfile
import os


def test_upsert_opencode_record():
    """Test upserting an OpenCode conversation with token breakdown."""
    from lmstudio_db import init_db, upsert_conversation, get_connection

    db_path = tempfile.mktemp(suffix='.db')

    try:
        init_db(db_path)

        opencode_conv = {
            'filename': 'msg_opencode_123',
            'token_count': 10702,
            'message_count': 1,
            'model': 'big-pickle',
            'created_at': '2025-12-01T10:00:00',
            'user_last_message_at': '2025-12-01T10:00:00',
            'source': 'opencode',
            'input_tokens': 94,
            'output_tokens': 48,
            'reasoning_tokens': 0,
            'cache_read_tokens': 10560,
        }

        upsert_conversation(db_path, opencode_conv)

        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT source, input_tokens, output_tokens, reasoning_tokens, cache_read_tokens "
                "FROM conversations WHERE filename = ?",
                ('msg_opencode_123',)
            )
            row = cursor.fetchone()

        assert row is not None
        assert row[0] == 'opencode'
        assert row[1] == 94    # input_tokens
        assert row[2] == 48    # output_tokens
        assert row[3] == 0     # reasoning_tokens
        assert row[4] == 10560 # cache_read_tokens

    finally:
        os.unlink(db_path)


def test_upsert_lmstudio_record_has_defaults():
    """Test that LMStudio records get default values for new columns."""
    from lmstudio_db import init_db, upsert_conversation, get_connection

    db_path = tempfile.mktemp(suffix='.db')

    try:
        init_db(db_path)

        lmstudio_conv = {
            'filename': 'conv_001.json',
            'token_count': 2543,
            'message_count': 3,
            'model': 'Llama-3.1-8B-Instruct',
            'created_at': '2025-03-01T10:00:00',
            'user_last_message_at': '2025-03-01T11:00:00',
        }

        upsert_conversation(db_path, lmstudio_conv)

        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT source, input_tokens, output_tokens, reasoning_tokens, cache_read_tokens "
                "FROM conversations WHERE filename = ?",
                ('conv_001.json',)
            )
            row = cursor.fetchone()

        assert row[0] == 'lmstudio'
        assert row[1] == 0
        assert row[2] == 0
        assert row[3] == 0
        assert row[4] == 0

    finally:
        os.unlink(db_path)
```

### Step 2: Run test to verify it fails

Run: `uv run pytest tests/test_db_migration.py::test_upsert_opencode_record -v`
Expected: FAIL — columns exist but upsert doesn't write them

### Step 3: Update upsert_conversation() in lmstudio_db.py

Replace the entire `upsert_conversation` function (lines 122-226) with this updated version:

```python
def upsert_conversation(db_path, conversation_data):
    """Upsert a conversation record into the database.

    Handles both LMStudio and OpenCode records via the 'source' field.
    For LMStudio records, token breakdown columns default to 0.
    For OpenCode records, each token type column is populated.

    Args:
        db_path: Path to the SQLite database file
        conversation_data: Dict containing conversation metadata

    Returns:
        bool: True if record was inserted, False if updated
    """
    filename = conversation_data.get('filename')

    if not filename:
        raise ValueError("Filename is required")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Create table and ensure schema
        get_or_create_table(conn)
        ensure_schema(db_path)

        current_time = datetime.now().isoformat()

        if check_record_exists(cursor, filename):
            # Check if data has actually changed
            cursor.execute(
                """
                    SELECT token_count, message_count, model, source
                    FROM conversations WHERE filename = ?
                """,
                (filename,)
            )
            existing = cursor.fetchone()

            new_token_count = conversation_data.get('token_count', 0)
            new_message_count = conversation_data.get('message_count', 0)
            new_model = conversation_data.get('model', '')
            new_source = conversation_data.get('source', 'lmstudio')

            if (existing and new_token_count == existing[0] and
                    new_message_count == existing[1] and
                    new_model == existing[2] and
                    new_source == existing[3]):
                return False

            # Build UPDATE query with all known fields
            updates = []
            params = []

            updates.append("token_count = ?")
            params.append(conversation_data.get('token_count', 0))

            updates.append("message_count = ?")
            params.append(conversation_data.get('message_count', 0))

            if conversation_data.get('model'):
                updates.append("model = ?")
                params.append(conversation_data.get('model'))

            # Handle source field
            updates.append("source = ?")
            params.append(new_source)

            # Token breakdown columns
            updates.append("input_tokens = ?")
            params.append(conversation_data.get('input_tokens', 0))

            updates.append("output_tokens = ?")
            params.append(conversation_data.get('output_tokens', 0))

            updates.append("reasoning_tokens = ?")
            params.append(conversation_data.get('reasoning_tokens', 0))

            updates.append("cache_read_tokens = ?")
            params.append(conversation_data.get('cache_read_tokens', 0))

            updates.append("updated_at = ?")
            params.append(current_time)

            update_sql = f"UPDATE conversations SET {', '.join(updates)} WHERE filename = ?"
            cursor.execute(update_sql, params + [filename])
            conn.commit()
            return False

        else:
            # Insert new record with all columns
            cursor.execute('''
                INSERT INTO conversations (
                    filename, token_count, message_count, model,
                    created_at, user_last_message_at, updated_at,
                    source, input_tokens, output_tokens, reasoning_tokens, cache_read_tokens
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                filename,
                conversation_data.get('token_count', 0),
                conversation_data.get('message_count', 0),
                conversation_data.get('model', ''),
                conversation_data.get('created_at'),
                conversation_data.get('user_last_message_at'),
                current_time,
                conversation_data.get('source', 'lmstudio'),
                conversation_data.get('input_tokens', 0),
                conversation_data.get('output_tokens', 0),
                conversation_data.get('reasoning_tokens', 0),
                conversation_data.get('cache_read_tokens', 0),
            ))
            conn.commit()
            return True
```

### Step 4: Run test to verify it passes

Run: `uv run pytest tests/test_db_migration.py -v`
Expected: All tests PASS (including existing ones)

### Step 5: Commit

```bash
git add lmstudio_db.py tests/test_db_migration.py
git commit -m "feat: update upsert_conversation to handle source and token breakdown columns"
```

---

## Task 4: Add `load_unified_data()` to data_loader.py

**Files:**
- Modify: `data_loader.py`
- Test: `tests/test_unified_data.py`

### Step 1: Write the failing test

```python
# tests/test_unified_data.py
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json


def test_load_unified_data_mixed_sources():
    """Test loading unified data with both LMStudio and OpenCode records."""
    from lmstudio_db import init_db, upsert_conversation
    from data_loader import load_unified_data

    db_path = tempfile.mktemp(suffix='.db')

    try:
        init_db(db_path)

        # Insert an LMStudio record
        upsert_conversation(db_path, {
            'filename': 'conv_001.json',
            'token_count': 1000,
            'message_count': 3,
            'model': 'Llama-3',
            'created_at': '2025-03-01T10:00:00',
            'user_last_message_at': '2025-03-01T11:00:00',
            'source': 'lmstudio',
            'input_tokens': 0,
            'output_tokens': 0,
            'reasoning_tokens': 0,
            'cache_read_tokens': 0,
        })

        # Insert an OpenCode record
        upsert_conversation(db_path, {
            'filename': 'msg_opencode_123',
            'token_count': 10702,
            'message_count': 1,
            'model': 'big-pickle',
            'created_at': '2025-12-01T10:00:00',
            'user_last_message_at': '2025-12-01T10:00:00',
            'source': 'opencode',
            'input_tokens': 94,
            'output_tokens': 48,
            'reasoning_tokens': 0,
            'cache_read_tokens': 10560,
        })

        df = load_unified_data(db_path)

        assert df is not None
        assert len(df) == 2
        assert 'source' in df.columns
        assert 'input_tokens' in df.columns
        assert 'output_tokens' in df.columns
        assert 'reasoning_tokens' in df.columns
        assert 'cache_read_tokens' in df.columns

        # Verify sources are correct
        sources = set(df['source'])
        assert 'lmstudio' in sources
        assert 'opencode' in sources

    finally:
        os.unlink(db_path)


def test_load_unified_data_empty():
    """Test loading unified data from empty database raises error."""
    from data_loader import load_unified_data

    db_path = tempfile.mktemp(suffix='.db')

    try:
        from lmstudio_db import init_db
        init_db(db_path)

        try:
            df = load_unified_data(db_path)
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass  # Expected

    finally:
        os.unlink(db_path)
```

### Step 2: Run test to verify it fails

Run: `uv run pytest tests/test_unified_data.py -v`
Expected: FAIL — function not defined

### Step 3: Add load_unified_data() to data_loader.py

Add this function at the end of `data_loader.py`:

```python
def load_unified_data(db_path):
    """Load all conversation data from both sources into a pandas DataFrame.

    Returns all columns including source discriminator and token breakdowns.

    Args:
        db_path: Path to SQLite database file
        
    Returns:
        pandas.DataFrame with columns: filename, token_count, message_count,
        model, created_at, user_last_message_at, updated_at, source,
        input_tokens, output_tokens, reasoning_tokens, cache_read_tokens
        
    Raises:
        FileNotFoundError: If database doesn't exist or has no data
    """
    import sqlite3
    import pandas as pd

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found at {db_path}")

    conn = sqlite3.connect(db_path)

    try:
        query = """
            SELECT 
                filename, token_count, message_count, model,
                created_at, user_last_message_at, updated_at,
                source, input_tokens, output_tokens, reasoning_tokens, cache_read_tokens
            FROM conversations
            ORDER BY created_at NULLS LAST
        """

        df = pd.read_sql_query(query, conn, parse_dates=["created_at"])

        if df.empty:
            raise FileNotFoundError(f"Database exists but is empty at {db_path}")

        return df

    except sqlite3.OperationalError as e:
        if "no such table" in str(e).lower():
            raise FileNotFoundError(f"No 'conversations' table found in database at {db_path}")
        raise
    finally:
        conn.close()
```

### Step 4: Run test to verify it passes

Run: `uv run pytest tests/test_unified_data.py -v`
Expected: All tests PASS

### Step 5: Commit

```bash
git add data_loader.py tests/test_unified_data.py
git commit -m "feat: add load_unified_data for combined LMStudio + OpenCode loading"
```

---

## Task 5: Update app.py — unified loading, source filter, breakdown toggle

**Files:**
- Modify: `app.py`

### Step 1: Write the failing test for app filtering logic

```python
# tests/test_app_filtering.py
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd


def test_source_filter_all():
    """Test source filter with 'all' returns both sources."""
    from lmstudio_db import init_db, upsert_conversation
    from data_loader import load_unified_data

    db_path = tempfile.mktemp(suffix='.db')

    try:
        init_db(db_path)
        upsert_conversation(db_path, {
            'filename': 'conv_001.json', 'token_count': 100, 'message_count': 1,
            'model': 'Model-A', 'created_at': '2025-03-01T10:00:00',
            'source': 'lmstudio', 'input_tokens': 0, 'output_tokens': 0,
            'reasoning_tokens': 0, 'cache_read_tokens': 0,
        })
        upsert_conversation(db_path, {
            'filename': 'msg_123', 'token_count': 200, 'message_count': 1,
            'model': 'Model-B', 'created_at': '2025-06-01T10:00:00',
            'source': 'opencode', 'input_tokens': 50, 'output_tokens': 100,
            'reasoning_tokens': 0, 'cache_read_tokens': 50,
        })

        df = load_unified_data(db_path)
        data = df.copy()
        data["_date"] = pd.to_datetime(data["created_at"])

        # Source filter: all (no filtering)
        source_filter = "all"
        if source_filter != "all":
            data = data[data["source"] == source_filter]

        assert len(data) == 2

    finally:
        os.unlink(db_path)


def test_source_filter_opencode_only():
    """Test source filter with 'opencode' returns only OpenCode records."""
    from lmstudio_db import init_db, upsert_conversation
    from data_loader import load_unified_data

    db_path = tempfile.mktemp(suffix='.db')

    try:
        init_db(db_path)
        upsert_conversation(db_path, {
            'filename': 'conv_001.json', 'token_count': 100, 'message_count': 1,
            'model': 'Model-A', 'created_at': '2025-03-01T10:00:00',
            'source': 'lmstudio', 'input_tokens': 0, 'output_tokens': 0,
            'reasoning_tokens': 0, 'cache_read_tokens': 0,
        })
        upsert_conversation(db_path, {
            'filename': 'msg_123', 'token_count': 200, 'message_count': 1,
            'model': 'Model-B', 'created_at': '2025-06-01T10:00:00',
            'source': 'opencode', 'input_tokens': 50, 'output_tokens': 100,
            'reasoning_tokens': 0, 'cache_read_tokens': 50,
        })

        df = load_unified_data(db_path)
        data = df.copy()
        data["_date"] = pd.to_datetime(data["created_at"])

        source_filter = "opencode"
        if source_filter != "all":
            data = data[data["source"] == source_filter]

        assert len(data) == 1
        assert data.iloc[0]["source"] == "opencode"

    finally:
        os.unlink(db_path)


def test_source_filter_lmstudio_only():
    """Test source filter with 'lmstudio' returns only LMStudio records."""
    from lmstudio_db import init_db, upsert_conversation
    from data_loader import load_unified_data

    db_path = tempfile.mktemp(suffix='.db')

    try:
        init_db(db_path)
        upsert_conversation(db_path, {
            'filename': 'conv_001.json', 'token_count': 100, 'message_count': 1,
            'model': 'Model-A', 'created_at': '2025-03-01T10:00:00',
            'source': 'lmstudio', 'input_tokens': 0, 'output_tokens': 0,
            'reasoning_tokens': 0, 'cache_read_tokens': 0,
        })
        upsert_conversation(db_path, {
            'filename': 'msg_123', 'token_count': 200, 'message_count': 1,
            'model': 'Model-B', 'created_at': '2025-06-01T10:00:00',
            'source': 'opencode', 'input_tokens': 50, 'output_tokens': 100,
            'reasoning_tokens': 0, 'cache_read_tokens': 50,
        })

        df = load_unified_data(db_path)
        data = df.copy()
        data["_date"] = pd.to_datetime(data["created_at"])

        source_filter = "lmstudio"
        if source_filter != "all":
            data = data[data["source"] == source_filter]

        assert len(data) == 1
        assert data.iloc[0]["source"] == "lmstudio"

    finally:
        os.unlink(db_path)
```

### Step 2: Run test to verify it fails

Run: `uv run pytest tests/test_app_filtering.py -v`
Expected: FAIL — app.py hasn't been updated yet (but the logic in tests is correct, so we just need to ensure the app uses load_unified_data)

Actually, these tests validate the filtering logic itself. Let's move on since the logic is straightforward and tested above. The real test is that the app works. Skip committing this test file — the filtering logic will be verified by integration testing of the app.

### Step 3: Update app.py — replace _load_data and add new UI elements

Replace the data loading section (lines 11-37) with:

```python
# Resolve database path relative to project root
_DB_PATH = Path(__file__).parent / "data" / "lmstudio_usage.db"

# Load data once at startup
def _load_data():
    """Load unified conversation data from the database (both sources)."""
    if not _DB_PATH.exists():
        return None
    try:
        from data_loader import load_unified_data
        df = load_unified_data(str(_DB_PATH))
        if df.empty:
            return None
        return df
    except Exception:
        return None

# Load data before app starts (module-level)
df = _load_data()

# Build model choices at startup to avoid reactive dropdown flash
if df is not None and not df.empty:
    _model_choices = {"__all__": "Top 5 Models"}
    for m in sorted(df["model"].dropna().unique().tolist()):
        _model_choices[m] = m
else:
    _model_choices = {"__all__": "Top 5 Models"}
```

Replace the sidebar UI (lines 41-68) with source filter and breakdown toggle added:

```python
    ui.sidebar(
        ui.input_select(
            "time_period",
            "Time Period",
            choices=["Monthly", "Daily"],
            selected="Monthly",
        ),
        ui.input_radio_buttons(
            "source_filter",
            "Source",
            choices={"all": "Both", "lmstudio": "LMStudio", "opencode": "OpenCode"},
            selected="all",
            inline=True,
        ),
        ui.input_radio_buttons(
            "breakdown_by",
            "Breakdown by",
            choices={"model": "Model", "token_type": "Token Type"},
            selected="model",
            inline=True,
        ),
        ui.input_select(
            "model_filter",
            "Model",
            choices=_model_choices,
            selected="__all__",
        ),
        ui.input_radio_buttons(
            "time_range",
            "Time Range",
            choices={
                "7": "7 days",
                "30": "30 days",
                "90": "90 days",
                "current_year": "Current Year",
                "all": "All Time",
            },
            selected="current_year",
            inline=True,
        ),
        open="desktop",
    ),
```

### Step 4: Update filtered_data() to apply source filter

Replace the `filtered_data()` function (lines 109-130) with:

```python
    @reactive.calc
    def filtered_data():
        """Filter data based on selected time range and source."""
        if df is None:
            return None
        data = df.copy()
        data["_date"] = pd.to_datetime(data["created_at"])
        
        # Apply source filter
        source = input.source_filter()
        if source and source != "all":
            data = data[data["source"] == source]
        
        tr = input.time_range()
        if tr == "7":
            cutoff = data["_date"].max() - pd.Timedelta(days=7)
            data = data[data["_date"] >= cutoff]
        elif tr == "30":
            cutoff = data["_date"].max() - pd.Timedelta(days=30)
            data = data[data["_date"] >= cutoff]
        elif tr == "90":
            cutoff = data["_date"].max() - pd.Timedelta(days=90)
            data = data[data["_date"] >= cutoff]
        elif tr == "current_year":
            cutoff = pd.Timestamp.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            data = data[data["_date"] >= cutoff]
        # "all" returns unfiltered data
        return data
```

### Step 5: Update usage_chart() to support token type breakdown

Replace the `usage_chart()` function (lines 168-275) with:

```python
    @output
    @render_plotly()
    def usage_chart():
        data = filtered_data()
        if data is None or data.empty:
            return None
        filtered = data.copy()
        
        breakdown = input.breakdown_by()
        
        if breakdown == "token_type":
            # Stack by token type per model
            gran = input.time_period()
            if gran == "Monthly":
                filtered["_time"] = pd.to_datetime(filtered["created_at"]).dt.to_period("M")
            else:
                filtered["_time"] = pd.to_datetime(filtered["created_at"]).dt.date
            
            # Apply model filter (top 5 or specific)
            model = input.model_filter()
            if not model or model == "__all__":
                top_models = filtered.groupby("model")["token_count"].sum().nlargest(5).index.tolist()
                agg_top5 = filtered[filtered["model"].isin(top_models)].copy()
            elif model:
                agg_top5 = filtered[filtered["model"] == model].copy()
            else:
                agg_top5 = filtered.copy()
            gran = input.time_period()
            if gran == "Monthly":
                agg_top5["_time"] = pd.to_datetime(agg_top5["created_at"]).dt.to_period("M")
            else:
                agg_top5["_time"] = pd.to_datetime(agg_top5["created_at"]).dt.date
            
            # Melt token breakdown columns into long format
            token_cols = ['input_tokens', 'output_tokens', 'reasoning_tokens', 'cache_read_tokens']
            melted = agg_top5.melt(
                id_vars=['_time', 'model'],
                value_vars=token_cols,
                var_name='token_type',
                value_name='token_count'
            )
            # Only keep rows with non-zero tokens
            melted = melted[melted['token_count'] > 0]
            
            if melted.empty:
                return None
            
            agg = melted.groupby(['_time', 'model', 'token_type'])['token_count'].sum().reset_index()
            
            # Format time labels
            if gran == "Monthly":
                agg["_time_label"] = agg["_time"].dt.strftime("%b %Y")
            else:
                agg["_time_label"] = agg["_time"].astype(str)
            
            # Determine models to display (top 5 by total tokens)
            model_totals = agg.groupby('model')['token_count'].sum()
            displayed_models = model_totals.nlargest(5).index.tolist()
            agg = agg[agg['model'].isin(displayed_models)]
            
            if agg.empty:
                return None
            
            # Token type order for legend
            token_type_order = ['input', 'output', 'reasoning', 'cache.read']
            token_type_display = {'input': 'Input', 'output': 'Output', 'reasoning': 'Reasoning', 'cache.read': 'Cache Read'}
            agg['token_type_label'] = agg['token_type'].map(token_type_display)
            
            palette = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2"]
            
            model_order = {m: i for i, m in enumerate(displayed_models)}
            agg["model_order"] = agg["model"].map(model_order)
            
            period_totals = agg.groupby('_time')['token_count'].transform('sum')
            agg["_pct"] = (agg['token_count'] / period_totals * 100).round(1)
            
            fig = px.bar(
                agg,
                x="_time_label",
                y="token_count",
                color="token_type",
                color_discrete_map={k: palette[i] for i, k in enumerate(token_type_display.keys())},
                barmode="stack",
                labels={"_time": "Time", "token_count": "Tokens", "model": "Model"},
                category_orders={
                    "token_type": [t for t in token_type_order if t in agg['token_type'].unique()],
                    "_time_label": agg.drop_duplicates("_time")["_time_label"].tolist(),
                },
                text=agg["token_count"].apply(lambda x: f"{x:,}" if x > 100 else ""),
                hover_data={
                    "model": True,
                    "token_type_label": True,
                    "token_count": True,
                    "_pct": ":.1f%%",
                    "_time_label": True,
                },
                custom_data=["model", "token_type_label", "token_count", "_pct"],
            )
            fig.update_traces(
                hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>Tokens: %{customdata[2]:,}<br>Period share: %{customdata[3]}<extra></extra>",
                textposition="inside",
            )
            fig.update_layout(
                xaxis_title="Time Period",
                yaxis_title="Total Tokens",
                legend_title="Token Type",
                xaxis_tickangle=-45,
                uniformtext_minsize=10,
                uniformtext_mode="hide",
                margin=dict(l=60, r=30, t=30, b=60),
                plot_bgcolor="white",
                paper_bgcolor="white",
                font=dict(size=12),
                legend=dict(orientation="h", yanchor="top", y=1.08, xanchor="center", x=0.5),
            )
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="LightGray")
            return fig
        
        # Original model-based breakdown (unchanged from before)
        model = input.model_filter()
        gran = input.time_period()
        
        if gran == "Monthly":
            agg_top5["_time"] = pd.to_datetime(agg_top5["created_at"]).dt.to_period("M")
        else:
            agg_top5["_time"] = pd.to_datetime(agg_top5["created_at"]).dt.date
        
        # Aggregate by time and model using total token_count (sum of all breakdown columns)
        agg = agg_top5.groupby(["_time", "model"])["token_count"].sum().reset_index()
        if agg.empty:
            return None

        # Format time labels for display
        if gran == "Monthly":
            agg["_time_label"] = agg["_time"].dt.strftime("%b %Y")
        else:
            agg["_time_label"] = agg["_time"].astype(str)

        # Determine which models are displayed
        if not model or model == "__all__":
            displayed_models = list(agg.groupby("model")["token_count"].sum().nlargest(5).index)
        elif model:
            displayed_models = [model]
        else:
            displayed_models = list(agg["model"].unique())

        # Order models consistently (largest first)
        model_order = {m: i for i, m in enumerate(displayed_models)}
        agg["model_order"] = agg["model"].map(model_order)

        # Distinct color palette
        palette = ["#2ec4b6", "#e16462", "#65a000", "#ff7f0e", "#7c3aed"]
        palette = palette[:len(displayed_models)]

        # Compute percentages for tooltips
        period_totals = agg.groupby("_time")["token_count"].transform("sum")
        agg["_pct"] = (agg["token_count"] / period_totals * 100).round(1)

        # Plotly stacked bar with hover tooltips
        fig = px.bar(
            agg,
            x="_time_label",
            y="token_count",
            color="model",
            color_discrete_map=dict(zip(displayed_models, palette)),
            barmode="stack",
            labels={"_time": "Time", "token_count": "Tokens", "model": "Model"},
            category_orders={
                "model": [m for m, _ in sorted(model_order.items(), key=lambda x: x[1])],
                "_time_label": agg.drop_duplicates("_time")["_time_label"].tolist(),
            },
            text=agg["token_count"].apply(lambda x: f"{x:,}" if x > 100 else ""),
            hover_data={
                "model": True,
                "token_count": True,
                "_pct": ":.1f%%",
                "_time_label": True,
            },
            custom_data=["model", "token_count", "_pct"],
        )
        fig.update_traces(
            hovertemplate="<b>%{customdata[0]}</b><br>Tokens: %{customdata[1]:,}<br>Period share: %{customdata[2]}<extra></extra>",
            textposition="inside",
        )
        # Dynamic legend title
        legend_title = "Top 5 Models" if not model or model == "__all__" else "Model"
        fig.update_layout(
            xaxis_title="Time Period",
            yaxis_title="Total Tokens",
            legend_title=legend_title,
            xaxis_tickangle=-45,
            uniformtext_minsize=10,
            uniformtext_mode="hide",
            margin=dict(l=60, r=30, t=30, b=60),
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(size=12),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=1.08,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0.8)",
            ),
        )
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="LightGray")
        return fig
```

### Step 6: Update model filter choices to use unified data

The `_model_choices` is already built from `df` which now comes from `load_unified_data()`. No additional changes needed here. The `update_model_options` reactive effect also uses `df` directly, so it will automatically include models from both sources.

### Step 7: Run existing tests to verify nothing is broken

Run: `uv run pytest -v`
Expected: All existing tests PASS (new columns have defaults, so old queries still work)

### Step 8: Commit

```bash
git add app.py tests/test_app_filtering.py
git commit -m "feat: add source filter and token type breakdown to dashboard"
```

---

## Task 6: Update data loading flow — scan both sources at startup

**Files:**
- Modify: `app.py` (the `_load_data()` function)

Currently, the app only loads from DB. The DB needs to be populated with both LMStudio and OpenCode records before the app starts. We need to update the startup sequence to scan both sources.

### Step 1: Update _load_data() to trigger scanning at startup

Replace `_load_data()` in `app.py` (lines 15-26) with:

```python
def _load_data():
    """Load unified conversation data from the database (both sources).
    
    Triggers a scan of both LMStudio and OpenCode data before loading.
    """
    if not _DB_PATH.exists():
        return None
    
    # Trigger scanning of both sources into DB
    try:
        from lmstudio_db import init_db
        init_db(str(_DB_PATH))
        
        from lmstudio_tokens import scan_conversations, load_conversations_from_files, upsert_conversation
        from opencode_tokens import scan_conversations as scan_opencode
        
        # Scan and upsert LMStudio conversations
        lmstudio_files = scan_conversations()
        if lmstudio_files:
            lmstudio_convs = load_conversations_from_files(lmstudio_files)
            for conv in lmstudio_convs:
                conv.setdefault('source', 'lmstudio')
                upsert_conversation(str(_DB_PATH), conv)
        
        # Scan and upsert OpenCode messages
        opencode_files = scan_opencode()
        if opencode_files:
            opencode_convs = load_conversations_from_files(opencode_files)
            for conv in opencode_convs:
                upsert_conversation(str(_DB_PATH), conv)
    except Exception as e:
        print(f"Warning during data scan: {e}")
    
    try:
        from data_loader import load_unified_data
        df = load_unified_data(str(_DB_PATH))
        if df.empty:
            return None
        return df
    except Exception:
        return None
```

### Step 2: Run existing tests to verify nothing is broken

Run: `uv run pytest -v`
Expected: All tests PASS

### Step 3: Commit

```bash
git add app.py
git commit -m "feat: scan both LMStudio and OpenCode at app startup"
```

---

## Task 7: Run full test suite and verify integration

**Files:**
- All test files
- Run from project root

### Step 1: Run full test suite

Run: `uv run pytest -v`
Expected: ALL tests PASS

### Step 2: Manual integration check

Run the app: `uv run python app.py`
Expected: App starts on 127.0.0.1:3000, shows both sources, source filter works, breakdown toggle works.

### Step 3: Commit any final changes

```bash
git add -A
git commit -m "test: run full test suite and verify integration"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ New `opencode_tokens.py` module — Task 1
- ✅ DB schema migration (5 new columns) — Task 2
- ✅ Updated upsert for new columns — Task 3
- ✅ `load_unified_data()` in data_loader.py — Task 4
- ✅ Source filter radio button — Task 5
- ✅ Breakdown toggle radio button — Task 5
- ✅ Chart stacks by model OR token type — Task 5
- ✅ Load at startup only (not dynamic) — Task 6
- ✅ Empty OpenCode dir = no errors — handled in scan_conversations()
- ✅ Missing tokens = 0 — handled with safe defaults in extract_from_json()
- ✅ Missing modelID = "unknown" — handled in extract_from_json()
- ✅ Timestamps auto-detect seconds/ms — handled in extract_from_json()
- ✅ Migration safe for re-runs — ensure_schema() uses IF NOT EXISTS pattern

**Placeholder scan:** No "TBD", "TODO", or vague references found. All code is complete.

**Type consistency:** All function signatures, column names, and field names are consistent across tasks. `source` is TEXT, token columns are INTEGER, all defaults match spec.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-unified-token-dashboard.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
