# 2026-05-27 — Tool Call Count Analytics

## Purpose

Track the number of tool calls per conversation/message in both LMStudio and OpenCode, stored alongside existing token usage data in `data/lmstudio_usage.db`.

## Design

### Architecture

Add a `tool_call_count INTEGER DEFAULT 0` column to the existing `conversations` table. This follows the same pattern used for `input_tokens`, `output_tokens`, `reasoning_tokens`, and `cache_read_tokens`.

### LMStudio Implementation

**File:** `lmstudio_tokens.py::extract_from_json()`

- Add a helper `_count_tool_calls(messages_list)` that recursively walks through each message's `versions[].steps[]`
- Count entries where `step.type == "toolStatus"`
- Include `'tool_call_count'` in the returned dict

### OpenCode Implementation

**File:** `opencode_db.py::_row_to_conversation()`

- Query the `part` table for rows where `json_extract(data, '$.type') = 'tool'`, linked by `message_id` to the current message
- Count those parts and set as `'tool_call_count'`

### Database Migration

**File:** `lmstudio_db.py::init_db()` and `get_or_create_table()`

- Add migration logic for the new column using the existing PRAGMA pattern (same as source, input_tokens, etc.)

## Data Flow

1. App starts or sync runs
2. LMStudio conversations scanned → tool call count extracted from JSON
3. OpenCode messages synced → tool call count derived from part table
4. All data upserted into `conversations` table with `tool_call_count` column
