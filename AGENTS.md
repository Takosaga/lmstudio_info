# LMStudio Usage Analytics — Agent Guide

## Setup & Commands

```bash
uv sync                              # install deps (Python 3.12)
uv run pytest                        # run all tests
uv run pytest tests/test_foo.py      # single test file
uv run python app.py                 # run Shiny dashboard (reads data/lmstudio_usage.db)
```

No lint/typecheck config exists. No pre-commit hooks.

## Architecture

Four modules, one data directory:

| Module | Role | Key entrypoints |
|---|---|---|
| `lmstudio_tokens.py` | Parse `~/.lmstudio/conversations/*.json` → dicts | `scan_conversations()`, `extract_from_json()`, `load_conversations_from_files()` |
| `lmstudio_db.py` | SQLite CRUD on `conversations` table | `init_db()`, `upsert_conversation()`, `get_usage_by_model()` |
| `data_loader.py` | Notebook/analysis interface (pandas DataFrames) | `load_usage_data()`, `get_token_statistics()`, `load_conversations_by_model()` |
| `app.py` | Shiny web dashboard | runs on `127.0.0.1:3000` in `if __name__ == "__main__"` block |

Data lives at `data/lmstudio_usage.db`. The app resolves it as `Path(__file__).parent / "data" / "lmstudio_usage.db"`.

## Gotchas

- Tests add `sys.path.insert(0, parent)` — always run from project root with `uv run pytest`.
- `app.py` loads the database once at module level; changes to the DB require a restart.
- `data_loader.py` default db path is `~/.lmstudio/usage.db`, NOT `data/lmstudio_usage.db`. Pass `db_path` explicitly when testing outside the app.
- Timestamps in LMStudio JSON may be seconds or milliseconds — `extract_from_json()` auto-detects by magnitude.
- The package name in `pyproject.toml` is `"projects"` (not `lmstudio_info`).
