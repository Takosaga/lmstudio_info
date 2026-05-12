# Unified Token Usage Dashboard — OpenCode + LMStudio

## Overview

Add OpenCode token usage data to the existing LMStudio Token Usage Dashboard. Both sources combine into a single unified dashboard with source filtering and optional token-type breakdown.

## Architecture

### Single SQLite `conversations` table with `source` discriminator

The existing table gains five new columns:

| Column | Type | Default | Purpose |
|---|---|---|---|
| `source` | TEXT | `'lmstudio'` | `'lmstudio'` or `'opencode'` |
| `input_tokens` | INTEGER | `0` | Input tokens for the message |
| `output_tokens` | INTEGER | `0` | Output tokens for the message |
| `reasoning_tokens` | INTEGER | `0` | Reasoning tokens (OpenCode only) |
| `cache_read_tokens` | INTEGER | `0` | Cache read tokens (OpenCode only) |

LMStudio records populate token breakdown columns as 0; total stays in existing `token_count`. OpenCode records set `token_count = sum(input + output + reasoning + cache_read)` with each breakdown column holding its respective value.

### New module: `opencode_tokens.py`

Mirrors `lmstudio_tokens.py` interface. Scans `~/.local/share/opencode/storage/message/*.json` files (organized under session ID subdirectories). Extracts token counts per message from OpenCode's JSON format. Same public API: `scan_conversations()`, `extract_from_json()`, `load_conversations_from_files()` returning dicts compatible with the existing DB upsert function.

### Data loader updates

New `load_unified_data()` in `data_loader.py` that UNIONs LMStudio and OpenCode records from the single `conversations` table into one pandas DataFrame. Existing `load_usage_data()` remains unchanged for backward compatibility.

### Dashboard updates (`app.py`)

**Source filter** — radio buttons in sidebar: "Both", "LMStudio", "OpenCode". Applied server-side via `filtered_data()`.

**Breakdown toggle** — new radio button "Breakdown by": "Model" (current behavior, groups by modelID) / "Token Type" (stacks input, output, reasoning, cache.read as separate bands per model).

### Data loading strategy

Load both sources at startup only (not dynamic reload), matching current LMStudio app behavior. The existing `if __name__ == "__main__"` block triggers a single scan + DB upsert cycle for all available sources.

## Error Handling

- Empty OpenCode directory → no records inserted, no errors
- Messages with no token data → all breakdown columns = 0, total = 0
- Missing modelID → stored as `"unknown"`
- Timestamps auto-detect seconds vs milliseconds by magnitude (existing behavior)
- DB migration (ALTER TABLE ADD COLUMN) is safe for re-runs (column exists check via PRAGMA)

## Testing

Existing tests in `tests/` continue to work. New tests cover:
- OpenCode token extraction from sample JSON files
- DB schema migration (adding columns to existing table)
- Unified data loading with mixed sources
- Source filter and breakdown toggle filtering logic
