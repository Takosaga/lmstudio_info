# LMStudio Usage Analytics

Extract, store, and analyze token usage data from LMStudio conversations. Visualize usage patterns in a Shiny dashboard with customizable filters.

## Overview

This package provides tools to extract conversation metadata (token counts, timestamps, models) from LMStudio's JSON exports, store them in a SQLite database, and query them using pandas DataFrames for analysis in Jupyter notebooks or Marimo.

## Installation

```bash
# Install dependencies
uv sync

# Or use pip
pip install -e ".[dev]"
```

## Quick Start

### 1. Extract Conversations from JSON Files

LMStudio stores conversations as JSON files in `~/.lmstudio/conversations/`. Use the extraction module to parse them:

```python
import lmstudio_tokens

# Find all conversation files
json_files = lmstudio_tokens.scan_conversations()
print(f"Found {len(json_files)} conversation file(s)")

# Extract metadata from specific or all files
conversations = lmstudio_tokens.load_conversations_from_files(json_files)

for conv in conversations[:3]:  # Preview first 3
    print(f"Model: {conv['model']} | Tokens: {conv['token_count']}")
```

### 2. Store in SQLite Database

```python
import lmstudio_tokens
from lmstudio_db import init_db, upsert_conversation

# Initialize database at your preferred location
db_path = '/data/.lmstudio_usage.db'

# Extract and import
json_files = lmstudio_tokens.scan_conversations()
conversations = lmstudio_tokens.load_conversations_from_files(json_files)

init_db(db_path)

for conv in conversations:
    upsert_conversation(db_path, conv)

print(f"Imported {len(conversations)} conversation(s) to database")
```

### 3. Analyze with pandas (Jupyter/Marimo)

Load data directly into a DataFrame for analysis:

```python
from data_loader import load_usage_data, get_token_statistics, get_connection
```

### 4. Run the Shiny Dashboard

Launch the interactive dashboard for visual analytics:

```bash
uv run shiny run app.py
# Opens at http://127.0.0.1:3000
```

Dashboard features:
- **Calendar heatmap** — GitHub-style token usage over time (52 weeks)
- **Stacked bar chart** — Model or token-type breakdown
- **KPI cards** — Total tokens, daily average, top model, tool calls
- **Time filters** — Daily/ monthly granularity, 7/30/90 days or current year
- **Multi-source** — Aggregates LMStudio, OpenCode, Pi, and Hermes sessions

```python
from data_loader import load_usage_data, get_token_statistics, get_connection

# Load all conversations as DataFrame
df = load_usage_data(db_path)
print(df.head())

# Summary statistics
stats = get_token_statistics()
print(f"Total tokens: {stats['total_tokens']}")
print(f"Conversations: {stats['conversation_count']}")
print(f"Avg tokens/conv: {stats['avg_tokens_per_conv']:.0f}")

# Group by model
usage_by_model = df.groupby('model')['token_count'].sum().sort_values(ascending=False)
print("\nTokens by Model:")
print(usage_by_model)

# Filter by date range (ISO format timestamps in database)
recent_usage = load_usage_data(
    db_path, 
    start_date='2024-01-01',  # Use datetime.fromisoformat() for ISO strings
    end_date='2024-12-31'
)
```

## Module Overview

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `lmstudio_tokens` | Extract JSON data | `scan_conversations()`, `extract_from_json()`, `load_conversations_from_files()` |
| `lmstudio_db` | SQLite storage | `init_db()`, `upsert_conversation()`, `get_usage_by_model()` |
| `opencode_db.py` | Sync OpenCode messages | `sync_opencode_tokens()` |
| `pi_db.py` | Sync Pi sessions | `sync_pi_tokens()` |
| `hermes_db.py` | Sync Hermes sessions | `sync_hermes_tokens()` |
| `data_loader` | Notebook interface | `load_usage_data()`, `load_unified_data()`, `get_token_statistics()` |
| `app.py` | Shiny dashboard | Web UI at `127.0.0.1:3000` |

## File Schema

The database stores conversations with these columns:

```sql
CREATE TABLE conversations (
    filename TEXT PRIMARY KEY,
    token_count INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    model TEXT DEFAULT '',
    created_at TIMESTAMP,
    user_last_message_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

## Advanced Usage

### Query by Model Only

```python
from data_loader import load_conversations_by_model

# Get all conversations for a specific model
gemma_conv = load_conversations_by_model(db_path, model='Gemma-7b-it')
print(gemma_conv.head())
```

### Custom Queries

Direct SQL queries are also supported:

```python
import sqlite3

conn = connect_connection(db_path)
cursor = conn.cursor()

# Get conversations with high token counts
cursor.execute("SELECT * FROM conversations WHERE token_count > 1000 ORDER BY token_count DESC LIMIT 10")
high_usage_rows = cursor.fetchall()

for row in high_usage_rows:
    print(f"{row[0]}: {row[1]} tokens, {row[2]} messages")
```

## Troubleshooting

### "Default database not found"

Set the `db_path` parameter explicitly:

```python
df = load_usage_data('/your/path/usage.db')
```

### Dashboard Not Reflecting Database Changes

The Shiny app (`app.py`) loads the database once at startup. After making database changes, restart the dashboard:

```bash
# Stop the server (Ctrl+C), then run again
uv run shiny run app.py
```

### Timestamp Format

LMStudio timestamps use milliseconds. They're automatically handled in extraction and converted to standard datetime format for queries.

## Notes

- **Unique Key**: Each conversation file is stored only once (by filename). Re-running `upsert_conversation()` only updates if data changed.
- **Default Path**: If `db_path` is not provided, defaults to `$HOME/.lmstudio_usage.db`.