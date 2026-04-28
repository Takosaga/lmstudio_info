# Daily Token Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daily token usage bar chart with model breakdown toggle to `lmstudio_visuals.py` (marimo).

**Architecture:** Query `conversations` table from SQLite, aggregate token counts by date, render with `mo.plots.bar`. A `mo.ui.dropdown` lets users filter by model or view all.

**Tech Stack:** Python 3.12, marimo 0.23.2, pandas, sqlite3, mo.plots (built-in plotly wrapper)

---

### Task 1: Add daily token usage chart cell to lmstudio_visuals.py

**Files:**
- Modify: `lmstudio_visuals.py` — add new marimo cell at end

- [ ] **Step 1: Add the chart cell to `lmstudio_visuals.py`**

Append this cell to the end of `lmstudio_visuals.py` (after the existing cells, before the `if __name__` block):

```python
@app.cell
def _(mo):
    import sqlite3
    import pandas as pd
    from datetime import datetime

    db_path = 'data/lmstudio_usage.db'

    # Load 2026 data with error handling
    if not __import__('os').path.exists(db_path):
        chart = mo.md("Database not found. Run the import cells first.")
        dropdown = mo.null
    else:
        conn = sqlite3.connect(db_path)
        try:
            query = """
                SELECT created_at, token_count, model
                FROM conversations
                WHERE created_at >= '2026-01-01'
            """
            df = pd.read_sql_query(query, conn)
        finally:
            conn.close()

        if df.empty:
            chart = mo.md("No token usage data for 2026 yet.")
            dropdown = mo.null
        else:
            # Truncate timestamps to date
            df['date'] = pd.to_datetime(df['created_at']).dt.date

            # Get unique models for dropdown
            models = sorted(df['model'].dropna().unique().tolist())

            # Dropdown: "All models" + individual models
            dropdown_options = [('All models', '')] + [(m, m) for m in models]
            dropdown = mo.ui.dropdown(options=dropdown_options, value='', label='Model')

            # Reactive chart function
            def render_chart(selected_model):
                filtered = df.copy()
                if selected_model:
                    filtered = filtered[filtered['model'] == selected_model]

                if filtered.empty:
                    return mo.md("No data for selected model.")

                daily = filtered.groupby('date')['token_count'].sum().reset_index()
                daily['date'] = pd.to_datetime(daily['date'])

                return mo.plots.bar(
                    daily,
                    x='date',
                    y='token_count',
                    title=f"Daily Token Usage{' — ' + selected_model if selected_model else ''}",
                    color='model' if not selected_model else None,
                )

            # Link dropdown to chart reactively
            chart = dropdown.output(render_chart)

    return (chart, dropdown,)
```

**Key implementation details:**
- Uses `pd.to_datetime(df['created_at']).dt.date` to truncate timestamps to dates
- Dropdown default is `''` (empty string = "All models")
- `dropdown.output(render_chart)` makes the chart reactive — it re-renders when dropdown value changes
- When a model is selected, `color` is set to `None` since all bars are the same model
- When "All models" is selected, `color='model'` adds model-colored segments

- [ ] **Step 2: Run the marimo app to verify**

Run: `.venv/bin/marimo run lmstudio_visuals.py`

Expected: App starts, shows the existing import cells, and the new chart cell renders a daily token usage bar chart. Dropdown filters by model.

- [ ] **Step 3: Commit**

```bash
git add lmstudio_visuals.py docs/superpowers/specs/2026-04-28-daily-token-usage-design.md
git commit -m "feat: add daily token usage chart with model breakdown toggle"
```
