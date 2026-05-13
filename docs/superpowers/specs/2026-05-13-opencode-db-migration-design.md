# OpenCode Token Data Migration — Design

## Overview

Migrate OpenCode token data collection from JSON file scanning (`opencode_tokens.py`) to direct SQLite queries against `opencode.db`. Keep LMStudio extraction unchanged.

## Scope

### What changes
- **Delete** `opencode_tokens.py` and `tests/test_opencode_tokens.py` — these scan `~/.local/share/opencode/conversations/*.json` files, which is slow and fragile.
- **Create** `opencode_db.py` — queries `opencode.db` directly for assistant messages with non-zero tokens, extracts model/token data from the JSON `data` column, and upserts into `lmstudio_usage.db`.
- **Update** `app.py` — replace `opencode_tokens` import/usage with `opencode_db`.

### What stays the same
- LMStudio extraction pipeline (`lmstudio_tokens.py` → `lmstudio_db.py` → `lmstudio_usage.db`) is untouched.
- `data_loader.py`, `tests/test_lmstudio_*`, and the Shiny dashboard UI are unchanged.

## Data Source: opencode.db

Location: `~/.local/share/opencode/opencode.db`

Table: `message` (~4,653 rows)

### Relevant columns
| Column | Type | Description |
|---|---|---|
| `id` | TEXT (PK) | Unique message identifier |
| `role` | TEXT | `'user'` or `'assistant'` |
| `time.created` | INTEGER | Timestamp in milliseconds |
| `data` | TEXT (JSON) | Message payload containing model and token info |

### Data JSON structure (`data` column)
```json
{
  "providerID": "string",
  "modelID": "string",
  "tokens": {
    "input": number,
    "output": number,
    "reasoning": number,
    "cache": { "read": number }
  }
}
```

### Filter criteria
Only include messages where:
- `role = 'assistant'`
- Total tokens > 0: `(tokens.input + tokens.output + tokens.reasoning + COALESCE(tokens.cache.read, 0)) > 0`

SQL query:
```sql
SELECT
    id,
    json_extract(data, '$.providerID') AS provider_id,
    json_extract(data, '$.modelID') AS model_id,
    json_extract(data, '$.tokens.input') AS input_tokens,
    json_extract(data, '$.tokens.output') AS output_tokens,
    json_extract(data, '$.tokens.reasoning') AS reasoning_tokens,
    json_extract(data, '$.tokens.cache.read') AS cache_read_tokens,
    time.created AS timestamp_ms
FROM message
WHERE role = 'assistant'
  AND (json_extract(data, '$.tokens.input', 0)
     + json_extract(data, '$.tokens.output', 0)
     + json_extract(data, '$.tokens.reasoning', 0)
     + COALESCE(json_extract(data, '$.tokens.cache.read'), 0)) > 0
```

## New Module: opencode_db.py

### Responsibilities
1. Connect to `opencode.db` (default: `~/.local/share/opencode/opencode.db`)
2. Execute the filtered query above
3. For each row, call `lmstudio_db.upsert_conversation()` to write into `lmstudio_usage.db`
4. Provide a `sync_opencode_tokens(db_path)` function — this is what `app.py` will call at startup

### API
```python
def sync_opencode_tokens(db_path: str | None = None) -> int:
    """Read assistant messages from opencode.db and upsert into lmstudio_usage.db.
    Returns the number of conversations synced."""
```

### Implementation details
- Use `sqlite3` module (stdlib), same as existing modules.
- Open opencode.db in read-only mode where possible (`uri=True` with `mode=ro`).
- Batch inserts via `upsert_conversation()` — no custom bulk operation needed; the existing function already handles upserts by message_id.
- Map opencode fields to the `Conversation` schema used by `lmstudio_db`:
  - `message.id` → `conversation_id` (primary key)
  - `model_id` → `model`
  - `timestamp_ms` → `timestamp`
  - tokens → `input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read_tokens`
  - `source = 'opencode'`

## Error Handling

- If `opencode.db` doesn't exist or is unreadable, log a warning and return 0 (graceful degradation — LMStudio data still works).
- If a row's `data` JSON is malformed or missing token fields, skip that row and continue.
- If `upsert_conversation()` fails for a row, log and continue (don't abort the batch).

## Testing

- Delete `tests/test_opencode_tokens.py`.
- Add `tests/test_opencode_db.py`:
  - Test `sync_opencode_tokens()` with a mock opencode.db containing known data
  - Verify correct filtering (only assistant messages with tokens > 0)
  - Verify upsert into lmstudio_usage.db produces correct rows
  - Test graceful handling of missing db file

## Migration Steps

1. Create `opencode_db.py`
2. Add `tests/test_opencode_db.py`
3. Update `app.py` — replace `import opencode_tokens` with `import opencode_db`, call `sync_opencode_tokens()` instead of `scan_conversations()`.
4. Delete `opencode_tokens.py` and `tests/test_opencode_tokens.py`
5. Run `uv run pytest` to verify all tests pass.
