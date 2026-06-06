# Pi Token Usage Integration Design

## Overview

Add pi session token usage as a third unified data source alongside `lmstudio` and `opencode`. A new module `pi_db.py` scans JSONL session files, extracts per-message token usage, and upserts into the existing `conversations` table. The dashboard already supports multi-source via `load_unified_data()` — no changes needed there.

## Schema Changes

Add `cache_write_tokens INTEGER DEFAULT 0` to the `conversations` table in `lmstudio_db.py`, following the same migration pattern as existing columns (`reasoning_tokens`, `cache_read_tokens`, etc.).

```
conversations table:
  filename, token_count, message_count, model, created_at,
  user_last_message_at, updated_at, source,
  input_tokens, output_tokens, reasoning_tokens, cache_read_tokens,
  cache_write_tokens,       ← NEW
  tool_call_count
```

## New Module: `pi_db.py`

Mirrors the structure of `opencode_db.py`:

| Function | Role |
|---|---|
| `_parse_timestamp_ms()` | Convert millisecond timestamps to naive UTC datetime (reused from opencode pattern) |
| `_extract_tokens(data_json)` | Extract `{input, output, reasoning, cacheRead, cacheWrite}` from a message's `usage` field |
| `_msg_to_conversation(line)` | Convert a JSONL line → dict compatible with `lmstudio_db.upsert_conversation()` |
| `sync_pi_tokens(db_path=None, lmstudio_db_path=None)` | Scan `~/.pi/agent/sessions/**/*.jsonl`, upsert assistant messages into lmstudio_usage.db |

### JSONL Structure

Each session file contains:
- Metadata lines: `type=session`, `type=model_change`, etc. (no usage)
- Message lines: `type=message` with nested `message` object containing `role`, `usage`, `content`, etc.

Token usage lives in `message.usage`:
```json
{
  "input": 20929,
  "output": 38,
  "cacheRead": 0,
  "cacheWrite": 0,
  "totalTokens": 20967,
  "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0 }
}
```

### Filtering Rules

- Only process lines with `type=message`
- Only extract from messages where `message.role == "assistant"`
- Only include messages that have a non-empty `message.usage` object
- Skip messages where all token counts are zero

### Timestamp Handling

Each message line has an ISO-format `timestamp` field (e.g. `2026-06-06T15:36:15.145Z`). This becomes the `created_at` value for the DB row. Since pi stores one row per assistant message, each row gets its own timestamp based on when that specific message was generated.

### Source Field

All pi records get `source: 'pi'`, enabling dashboard filtering alongside `'lmstudio'` and `'opencode'`.

## Integration Points

| File | Change |
|---|---|
| `lmstudio_db.py` | Add `cache_write_tokens` column + schema migration in `init_db()` |
| `pi_db.py` | **NEW** — pi session scanner & sync |
| `app.py` `_load_all_sources()` | Add pi sync step (try/except, skip if no sessions dir) |
| `data_loader.py` | No changes — `load_unified_data()` already queries all sources |

## Data Flow

```
~/.pi/agent/sessions/**/*.jsonl
        │
        ▼
   pi_db.py: sync_pi_tokens()
        │
        ├── reads each JSONL line
        ├── filters type=message + role=assistant + has usage
        ├── extracts {input, output, reasoning, cacheRead, cacheWrite}
        └── upserts into lmstudio_usage.db.conversations (source='pi')

app.py startup:
  1. scan LMStudio conversations → upsert (source='lmstudio')
  2. sync OpenCode tokens → upsert (source='opencode')
  3. sync Pi sessions → upsert (source='pi')          ← NEW
  4. load_unified_data() → dashboard DataFrame
```

## Error Handling

- Missing session directory: log warning, return 0 synced — no crash
- Malformed JSONL lines: skip and continue (same pattern as opencode)
- DB write failures per row: log warning, skip that row, continue (same pattern)
- All sync steps wrapped in try/except in `app.py`, matching existing behavior

## Testing

New file `tests/test_pi_db.py` covering:

- `_extract_tokens()` with various usage shapes (full data, zero values, missing keys)
- `_msg_to_conversation()` — valid message, missing usage, wrong role, zero tokens
- `sync_pi_tokens()` — empty dir, no sessions, actual files (mocked filesystem)
- Schema migration: verify `cache_write_tokens` column exists after `init_db()`

## Implementation Order

1. Add `cache_write_tokens` column to `lmstudio_db.py` schema + migration
2. Create `pi_db.py` with extraction and sync logic
3. Update `app.py` `_load_all_sources()` to include pi sync
4. Add tests in `tests/test_pi_db.py`
