# LMStudio Usage Analytics — Agent Guide

## Setup & Commands

```bash
uv sync                              # install deps (Python 3.12)
uv run pytest                        # run all tests
uv run pytest tests/test_foo.py      # single test file
uv run shiny run app.py              # run Shiny dashboard (reads data/lmstudio_usage.db)
```

No lint/typecheck config. No pre-commit hooks.

## Recent Changes

- **2026-07-06**: Chart now filters models by 10M token threshold, with fallback to top 5 if none exceed threshold.
- **2026-06-27**: Database schema updated, added Hermes session sync.

## Architecture

Seven modules, one data directory:

| Module | Role | Key entrypoints |
|---|---|---|
| `lmstudio_tokens.py` | Parse `~/.lmstudio/conversations/*.json` → dicts | `scan_conversations()`, `extract_from_json()`, `load_conversations_from_files()` |
| `lmstudio_db.py` | SQLite CRUD on `conversations` table | `init_db()`, `upsert_conversation()`, `get_usage_by_model()` |
| `opencode_db.py` | Sync OpenCode messages from `~/.local/share/opencode/opencode.db` → lmstudio_usage.db | `sync_opencode_tokens()` |
| `pi_db.py` | Sync Pi session JSONL files | `sync_pi_tokens()` |
| `hermes_db.py` | Sync Hermes sessions from `state.db` | `sync_hermes_tokens()` |
| `data_loader.py` | Notebook/analysis interface (pandas DataFrames) | `load_usage_data()`, `load_unified_data()`, `get_token_statistics()` |
| `app.py` | Shiny web dashboard | scans all sources at startup, runs on `127.0.0.1:3000` |

Data lives at `data/lmstudio_usage.db`. The app resolves it as `Path(__file__).parent / "data" / "lmstudio_usage.db"`.

## Gotchas

- Tests add `sys.path.insert(0, parent)` — always run from project root with `uv run pytest`.
- `app.py` loads the database once at module level; changes to the DB require a restart.
- `data_loader.py` default db path is `~/.lmstudio/usage.db`, NOT `data/lmstudio_usage.db`. Pass `db_path` explicitly when testing outside the app.
- Timestamps in LMStudio JSON may be seconds or milliseconds — `extract_from_json()` auto-detects by magnitude (threshold: 3999999999).
- The package name in `pyproject.toml` is `"projects"` (not `lmstudio_info`).
- `opencode_tokens.py` was removed; use `opencode_db.sync_opencode_tokens()` instead.
- Conversations have a `source` column: `'lmstudio'` or `'opencode'`. Use `load_unified_data()` to query both sources together.
- Dashboard chart filters models by 10M token threshold (fallback to top 5). Source: AGENTS.md recent changes.
