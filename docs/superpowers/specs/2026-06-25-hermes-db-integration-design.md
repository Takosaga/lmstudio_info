# Hermes DB Integration Design

## Goal

Add Hermes Agent session data to the lmstudio_info dashboard by syncing from its local SQLite database (`~/.hermes/state.db`).

## Background

Hermes Agent (NousResearch) stores all session metadata in a single SQLite database at `~/.hermes/state.db`. The `sessions` table already contains aggregated token counts per session — input tokens, output tokens, reasoning tokens, cache read/write tokens, tool call count, message count, model name, timestamps, and source tagging.

This eliminates the need for per-message parsing (unlike Pi's JSONL approach). Each session row maps directly to one conversation row in lmstudio_usage.db.

## Architecture

```
~/.hermes/state.db (SQLite)
    │
    ▼
hermes_db.py
    sync_hermes_tokens()
        reads sessions table
        normalizes model names
        converts timestamps
    │
    ▼
lmstudio_usage.db.conversations (via upsert_conversation)
    │
    ▼
app.py → data_loader.load_unified_data() → dashboard display
```

## Design Decisions

### 1. Session-level aggregates only
Each Hermes session = one row in `conversations`. No per-message parsing needed since the `sessions` table already has aggregated token counts. This matches the LMStudio pattern (one JSON file = one conversation).

### 2. Filename = session ID
Hermes session IDs are unique primary keys (e.g., `20260624_194845_f20214`). They serve directly as the `filename` primary key in the conversations table. No collision risk.

### 3. Source = 'hermes'
All synced rows get `source='hermes'`. The existing `sessions.source` column (cli, signal, telegram, discord, etc.) is not preserved — it would add unnecessary granularity to the dashboard. If needed later, a new column can be added.

### 4. Model name normalization
Same regex as other syncs: `^[a-zA-Z][a-zA-Z0-9_-]+/` strips provider/community prefixes (e.g., `lmstudio-community/qwen-7b` → `qwen-7b`). This ensures the same model merges correctly across all sources.

### 5. Timestamp conversion
Hermes stores timestamps as REAL unix floats (`started_at`, `ended_at`). These convert directly to Python datetime objects via `datetime.fromtimestamp()` and are stored as naive UTC datetimes in the conversations table (matching existing convention).

### 6. Token fields mapping
| Hermes field | Conversations field | Notes |
|---|---|---|
| `input_tokens` | `input_tokens` | Direct copy |
| `output_tokens` | `output_tokens` | Direct copy |
| `reasoning_tokens` | `reasoning_tokens` | Direct copy |
| `cache_read_tokens` | `cache_read_tokens` | Direct copy |
| `cache_write_tokens` | `cache_write_tokens` | Direct copy |
| `tool_call_count` | `tool_call_count` | Direct copy |
| `message_count` | `message_count` | Direct copy |
| sum of all tokens | `token_count` | Computed at upsert time |

### 7. Error handling
If `~/.hermes/state.db` doesn't exist or can't be opened, the sync silently returns 0 (matching existing pattern in `_load_all_sources()`).

## Files to Create/Modify

| File | Action | Description |
|---|---|---|
| `hermes_db.py` | **Create** | Sync function: reads Hermes SQLite, upserts into conversations table |
| `app.py` | Modify | Add `sync_hermes_tokens()` call in `_load_all_sources()` |
| `tests/test_hermes_db.py` | **Create** | Tests for extraction, conversion, full sync with mock DB |

## Implementation Notes

- Follow the exact pattern of `opencode_db.py` and `pi_db.py`
- Use `lmstudio_db.init_db()` and `lmstudio_db.upsert_conversation()` for DB access
- Keep the function signature consistent: `sync_hermes_tokens(db_path=None, lmstudio_db_path=None)`
- Default db_path: `~/.hermes/state.db`
