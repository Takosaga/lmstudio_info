# Tool Call Count Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track tool call counts per conversation/message in both LMStudio and OpenCode data sources.

**Architecture:** Add `tool_call_count INTEGER DEFAULT 0` column to the existing `conversations` table. Extract counts from LMStudio JSON (toolStatus steps) and OpenCode part table (type='tool' parts).

**Tech Stack:** Python, SQLite, pandas, pytest

---

## File Structure

| File | Responsibility |
|---|---|
| `lmstudio_db.py` | Add `tool_call_count` column migration |
| `lmstudio_tokens.py` | Count toolStatus steps in LMStudio JSON messages |
| `opencode_db.py` | Query part table for tool-type parts per message |
| `tests/test_extraction.py` | Tests for LMStudio tool call counting |
| `tests/test_opencode_db.py` | Tests for OpenCode tool call counting |

---

### Task 1: Add tool_call_count column migration to lmstudio_db.py

**Files:**
- Modify: `lmstudio_db.py:78-91` (init_db migration)
- Modify: `lmstudio_db.py:147-161` (get_or_create_table migration)

- [ ] **Step 1: Add tool_call_count to init_db() migration list**

In `lmstudio_db.py:init_db()`, line ~80, add the new column to the `new_columns` list:

```python
new_columns = [
    ('source', "TEXT DEFAULT 'lmstudio'"),
    ('input_tokens', 'INTEGER DEFAULT 0'),
    ('output_tokens', 'INTEGER DEFAULT 0'),
    ('reasoning_tokens', 'INTEGER DEFAULT 0'),
    ('cache_read_tokens', 'INTEGER DEFAULT 0'),
    ('tool_call_count', 'INTEGER DEFAULT 0'),
]
```

- [ ] **Step 2: Add tool_call_count to get_or_create_table() migration list**

In `lmstudio_db.py:get_or_create_table()`, line ~150, add the same column to the `new_columns` list (identical change as Step 1).

- [ ] **Step 3: Run tests to verify no regressions**

Run: `uv run pytest tests/test_database.py -v`
Expected: All existing tests pass.

---

### Task 2: Implement tool call counting in LMStudio JSON extraction

**Files:**
- Modify: `lmstudio_tokens.py`

- [ ] **Step 1: Write failing test for tool status counting**

Add to `tests/test_extraction.py`:

```python
def test_extract_tool_call_count():
    """Test extraction of tool call count from toolStatus steps."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    json_data = {
        "tokenCount": 2065,
        "messages": [
            {"role": "user", "content": "Hello"},
            {
                "role": "assistant",
                "versions": [
                    {
                        "steps": [
                            {"genInfo": {"stats": {"promptTokensCount": 100, "predictedTokensCount": 50}}},
                            {"type": "toolStatus", "callId": "call_1", "statusState": {"status": {"type": "toolCallSucceeded"}}},
                            {"type": "toolStatus", "callId": "call_2", "statusState": {"status": {"type": "toolCallSucceeded"}}},
                        ]
                    }
                ]
            },
            {
                "role": "assistant",
                "versions": [
                    {
                        "steps": [
                            {"type": "toolStatus", "callId": "call_3", "statusState": {"status": {"type": "toolCallSucceeded"}}},
                        ]
                    }
                ]
            }
        ],
        "createdAt": 1709251200
    }
    
    import json as json_mod
    with patch('lmstudio_tokens.open', new_callable=mock_open,
               read_data=json_mod.dumps(json_data)) as mock_file:
        
        file_path = str(test_dir / 'test.json')
        result = lmstudio_tokens.extract_from_json(file_path)

        assert result['tool_call_count'] == 3


def test_extract_tool_call_count_zero():
    """Test tool call count is 0 when no toolStatus steps present."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    json_data = {
        "tokenCount": 100,
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ],
        "createdAt": 1709251200
    }
    
    import json as json_mod
    with patch('lmstudio_tokens.open', new_callable=mock_open,
               read_data=json_mod.dumps(json_data)) as mock_file:
        
        file_path = str(test_dir / 'test.json')
        result = lmstudio_tokens.extract_from_json(file_path)

        assert result['tool_call_count'] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_extraction.py::test_extract_tool_call_count -v`
Expected: FAIL — `KeyError: 'tool_call_count'` or assertion failure.

- [ ] **Step 3: Implement _count_tool_calls helper and add to return dict**

Add the helper function inside `extract_from_json()` in `lmstudio_tokens.py`, right before the `return` statement (after `_collect_geninfo_stats`):

```python
def _count_tool_calls(obj):
    """Recursively count toolStatus steps in a message tree."""
    count = 0
    if isinstance(obj, dict):
        if obj.get('type') == 'toolStatus':
            count += 1
        for v in obj.values():
            count += _count_tool_calls(v)
    elif isinstance(obj, list):
        for item in obj:
            count += _count_tool_calls(item)
    return count

tool_call_count = _count_tool_calls(messages_list)
```

Add `'tool_call_count': tool_call_count` to the returned dict at line ~102:

```python
return {
    'filename': Path(file_path).name,
    'token_count': total_tokens,
    'message_count': message_count,
    'model': model_name,
    'created_at': created_at,
    'user_last_message_at': user_last_message_at,
    'input_tokens': input_tokens,
    'output_tokens': output_tokens,
    'reasoning_tokens': 0,
    'cache_read_tokens': 0,
    'tool_call_count': tool_call_count,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_extraction.py::test_extract_tool_call_count tests/test_extraction.py::test_extract_tool_call_count_zero -v`
Expected: Both PASS.

- [ ] **Step 5: Run all extraction tests to verify no regressions**

Run: `uv run pytest tests/test_extraction.py -v`
Expected: All tests pass.

---

### Task 3: Implement tool call counting in OpenCode part table queries

**Files:**
- Modify: `opencode_db.py`

- [ ] **Step 1: Write failing test for OpenCode tool call counting**

Add to `tests/test_opencode_db.py`:

```python
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
            index INTEGER NOT NULL,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_opencode_db.py::test_sync_opencode_tokens_with_tool_calls -v`
Expected: FAIL — column 'tool_call_count' does not exist.

- [ ] **Step 3: Implement tool call counting in _row_to_conversation()**

Add a helper function at module level in `opencode_db.py` (after `_extract_tokens`, around line 53):

```python
def _count_tool_calls(opencode_db_path: str, message_id: str) -> int:
    """Count tool-type parts for a given message.

    Args:
        opencode_db_path: Path to the opencode.db file.
        message_id: The message ID to query parts for.

    Returns:
        Number of parts where json_extract(data, '$.type') = 'tool'.
    """
    try:
        conn = sqlite3.connect(f"file:{opencode_db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM part
            WHERE message_id = ?
              AND json_extract(data, '$.type') = 'tool'
            """,
            (message_id,),
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except sqlite3.Error:
        return 0
```

Modify `_row_to_conversation()` in `opencode_db.py` to accept the opencode db path and call the new function. The function signature needs to change — update `sync_opencode_tokens()` to pass the db_path to a modified `_row_to_conversation()`:

In `_row_to_conversation(row, opencode_db_path)`, after extracting `msg_id` (line 65), add:

```python
tool_call_count = _count_tool_calls(opencode_db_path, msg_id)
```

Add `'tool_call_count': tool_call_count` to the returned dict at line ~95:

```python
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
    "tool_call_count": tool_call_count,
}
```

Update the call site in `sync_opencode_tokens()` (line ~169):

```python
conv = _row_to_conversation(row, db_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_opencode_db.py::test_sync_opencode_tokens_with_tool_calls -v`
Expected: PASS.

- [ ] **Step 5: Run all opencode tests to verify no regressions**

Run: `uv run pytest tests/test_opencode_db.py -v`
Expected: All tests pass.

---

### Task 4: Update existing opencode tests for new column

**Files:**
- Modify: `tests/test_opencode_db.py`

- [ ] **Step 1: Update _create_mock_opencode_db to include part table**

In the existing `_create_mock_opencode_db()` function, add part table creation and some tool parts:

```python
# After the message table CREATE, add:
c.execute("""
    CREATE TABLE part (
        id TEXT PRIMARY KEY,
        message_id TEXT NOT NULL,
        index INTEGER NOT NULL,
        data TEXT NOT NULL
    )
""")

# Add tool parts for msg_test_001 (2 tool calls)
c.execute(
    "INSERT INTO part VALUES (?, ?, ?, ?)",
    ("part_a", "msg_test_001", 0, json.dumps({"type": "tool", "callID": "ca1", "tool": "glob"})),
)
c.execute(
    "INSERT INTO part VALUES (?, ?, ?, ?)",
    ("part_b", "msg_test_001", 1, json.dumps({"type": "tool", "callID": "ca2", "tool": "read_file"})),
)

# Add tool parts for msg_test_004 (1 tool call)
c.execute(
    "INSERT INTO part VALUES (?, ?, ?, ?)",
    ("part_c", "msg_test_004", 0, json.dumps({"type": "tool", "callID": "ca3", "tool": "bash"})),
)
```

- [ ] **Step 2: Update test_sync_opencode_tokens_basic to verify tool_call_count**

Add assertions after the existing assertions in `test_sync_opencode_tokens_basic`:

```python
# Check tool_call_count for msg_test_001 (2 tool calls)
c.execute("SELECT tool_call_count FROM conversations WHERE filename = 'msg_test_001'")
assert c.fetchone()[0] == 2

# Check tool_call_count for msg_test_004 (1 tool call)
c.execute("SELECT tool_call_count FROM conversations WHERE filename = 'msg_test_004'")
assert c.fetchone()[0] == 1
```

- [ ] **Step 3: Run all opencode tests**

Run: `uv run pytest tests/test_opencode_db.py -v`
Expected: All tests pass.

---

### Task 5: Update data_loader.py to include tool_call_count in queries

**Files:**
- Modify: `data_loader.py`

- [ ] **Step 1: Verify load_unified_data returns tool_call_count**

The existing `load_unified_data()` uses `SELECT * FROM conversations`, so it will automatically include the new column. No code changes needed — just verify with a test.

Add to `tests/test_loader.py` (or create if it doesn't exist):

```python
def test_load_unified_data_includes_tool_call_count():
    """Verify load_unified_data returns tool_call_count column."""
    import sqlite3
    
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    lmstudio_db.init_db(db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "INSERT INTO conversations (filename, token_count, message_count, model, created_at, source, tool_call_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("test.json", 100, 2, "test-model", "2024-01-01", "lmstudio", 5),
    )
    conn.commit()
    conn.close()
    
    from data_loader import load_unified_data
    df = load_unified_data(db_path)
    
    assert 'tool_call_count' in df.columns
    assert df['tool_call_count'].iloc[0] == 5
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_loader.py -v`
Expected: Test passes.

---

### Task 6: Final integration test and cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass across all test files.

- [ ] **Step 2: Commit all changes**

```bash
git add lmstudio_db.py lmstudio_tokens.py opencode_db.py data_loader.py tests/test_extraction.py tests/test_opencode_db.py tests/test_loader.py
git commit -m "feat: add tool call count tracking for LMStudio and OpenCode"
```
