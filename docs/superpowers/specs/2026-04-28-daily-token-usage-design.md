# Daily Token Usage Design

**Date:** 2026-04-28

## Goal

Add a daily token usage bar chart to `lmstudio_visuals.py` (marimo) showing tokens used per day since Jan 1, 2026, with a model breakdown toggle.

## Design

### Data Source
- Query `conversations` table from `data/lmstudio_usage.db`
- Filter by `created_at >= '2026-01-01'`
- Group by date (truncate `created_at` to day), sum `token_count`
- For model breakdown: group by date + `model`

### Components
1. **Model dropdown** (`mo.ui.dropdown`): default "All models", lists each unique model from 2026 data
2. **Daily bar chart** (`mo.plots.bar`): x=date, y=token_count, colored by model (when breakdown active)
3. **Reactive update**: chart re-renders when dropdown selection changes

### Implementation
- Add as a new cell in `lmstudio_visuals.py` (marimo app)
- Use existing `data_loader.py` / `lmstudio_db.py` for database access
- Use `mo.plots.bar` (marimo's built-in plotly wrapper) — no new dependencies
- Reuse existing data loading pattern: `sqlite3.connect(db_path)` + `pd.read_sql_query`
- Aggregate with pandas: `df.groupby(date_col).sum()`

### Error Handling
- If no 2026 data: display `mo.md("No token usage data for 2026 yet.")`
- If database missing: display `mo.md("Database not found. Run the import cells first.")`

### File Changes
- **Modify:** `lmstudio_visuals.py` — add new marimo cell with chart logic
