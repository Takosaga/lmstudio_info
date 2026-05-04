# Shiny Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-page Shiny dashboard showing LMStudio token usage as a stacked bar chart with summary cards.

**Architecture:** Single `app.py` file using Shiny UI + server pattern. Data loaded from `data/lmstudio_usage.db` via existing `data_loader.load_usage_data()`. Chart rendered with Plotly, styled with Shiny cards.

**Tech Stack:** Python 3.12+, shiny, plotly, pandas (all already in `pyproject.toml`)

---

### File Structure

- **Create:** `app.py` — entire dashboard (Shiny app)
- **No new dependencies** — all use existing `pyproject.toml` packages
- **Reuses:** `data_loader.py` (`load_usage_data`), `lmstudio_db.py` (database layer)

---

### Task 1: Create `app.py` with Shiny UI layout

**Files:**
- Create: `app.py`

- [ ] **Step 1: Write the complete `app.py`**

```python
"""LMStudio Token Usage Dashboard — local shiny app."""

from pathlib import Path

import pandas as pd
import plotly.express as px
from shiny import App, ui, render
from shiny.types import WarnOnExpr

# Resolve database path relative to project root
_DB_PATH = Path(__file__).parent / "data" / "lmstudio_usage.db"

# Load data once at startup
def _load_data():
    """Load conversation data from the database."""
    if not _DB_PATH.exists():
        return None
    from data_loader import load_usage_data
    try:
        df = load_usage_data(str(_DB_PATH))
        if df.empty:
            return None
        return df
    except Exception:
        return None

# Load data before app starts (module-level)
df = _load_data()

# --- UI ---
app_ui = ui.page_fluid(
    ui.h2("LMStudio Token Usage", class_="text-center mb-4"),
    # Summary cards row
    ui.row(
        ui.column(
            6,
            ui.card(
                ui.card_header("Total Tokens"),
                ui.output_text("total_tokens", width="100%"),
                class_="text-center",
            ),
        ),
        ui.column(
            6,
            ui.card(
                ui.card_header("Average Monthly Tokens"),
                ui.output_text("avg_monthly", width="100%"),
                class_="text-center",
            ),
        ),
    ),
    # Controls
    ui.row(
        ui.column(
            4,
            ui.input_select("granularity", "Granularity", choices=["Daily", "Monthly"]),
        ),
        ui.column(
            4,
            ui.input_select("model_filter", "Model", choices=["All models"]),
        ),
    ),
    # Chart
    ui.card(
        ui.card_header("Token Usage Over Time"),
        ui.output_plot("usage_chart"),
    ),
)

# --- Server ---
def server(input, output, session):
    @output
    @render.text
    def total_tokens():
        if df is None:
            return "No data available."
        total = int(df["token_count"].sum())
        return f"{total:,}"

    @output
    @render.text
    def avg_monthly():
        if df is None:
            return "No data available."
        df_copy = df.copy()
        df_copy["_month"] = pd.to_datetime(df_copy["created_at"]).dt.to_period("M")
        months = df_copy["_month"].nunique()
        if months == 0:
            return "No data available."
        avg = int(df["token_count"].sum() / months)
        return f"{avg:,}"

    @output
    @render.plot
    def usage_chart():
        if df is None:
            return None
        filtered = df.copy()
        # Model filter
        model = input.model_filter()
        if model and model != "All models":
            models_list = list(filtered["model"].dropna().unique())
            if model in models_list:
                filtered = filtered[filtered["model"] == model]
        # Granularity
        gran = input.granularity()
        if gran == "Monthly":
            filtered["_time"] = pd.to_datetime(filtered["created_at"]).dt.to_period("M").astype(str)
        else:
            filtered["_time"] = pd.to_datetime(filtered["created_at"]).dt.date.astype(str)
        # Aggregate
        agg = filtered.groupby(["_time", "model"])["token_count"].sum().reset_index()
        if agg.empty:
            return None
        # Plotly stacked bar
        fig = px.bar(
            agg,
            x="_time",
            y="token_count",
            color="model",
            barmode="stack",
            labels={"_time": "Time", "token_count": "Tokens", "model": "Model"},
        )
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Tokens",
            legend_title="Model",
            xaxis_tickangle=-45,
        )
        return fig

    # Update model filter options reactively
    @ui.effect
    def update_model_options():
        if df is None:
            return
        models = sorted(df["model"].dropna().unique().tolist())
        choices = [("All models", "")] + [(m, m) for m in models]
        ui.update_select("model_filter", choices=choices)

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000, debug=True)
```

- [ ] **Step 2: Verify the file was created**

Run: `ls -la /home/takosaga/Projects/lmstudio_info/app.py`
Expected: File exists, non-empty.

- [ ] **Step 3: Check imports resolve**

Run: `uv run python -c "from data_loader import load_usage_data; print('OK')"`
Expected: `OK` (or error if DB doesn't exist, which is fine at this stage).

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add shiny dashboard with stacked bar chart and summary cards"
```

---

### Task 2: Test the dashboard

**Files:**
- No test files needed — this is a live dashboard app
- Verification is manual: run the app and check it renders

- [ ] **Step 1: Run the app**

Run: `uv run shiny run app.py`

Expected output:
```
Shiny app running at http://127.0.0.1:3000
```

- [ ] **Step 2: Verify in browser**

Open `http://127.0.0.1:3000` and check:
- Header "LMStudio Token Usage" is displayed
- Two summary cards show numeric values (total tokens, average monthly)
- Dropdown controls for "Granularity" (Daily/Monthly) and "Model" (All models + list)
- Stacked bar chart renders with model-colored segments
- Switching granularity toggles between daily/monthly bars
- Switching model filter updates the chart

- [ ] **Step 3: Test error path (if no DB)**

Temporarily rename `data/lmstudio_usage.db`, run the app, and verify:
- Cards show "No data available."
- No crash or traceback

Restore: `mv data/lmstudio_usage.db.bak data/lmstudio_usage.db`

- [ ] **Step 4: Stop the app**

Press `Ctrl+C` in the terminal.

---

### Task 3: Add a run script to `pyproject.toml`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `[project.scripts]` entry**

Add to `pyproject.toml` under `[project]`:
```toml
[project.scripts]
lmstudio-dashboard = "app:app"
```

Actually, for `uv run`, the simpler approach is already working via `uv run shiny run app.py`. Instead, add a convenience entry:

```toml
[tool.uv]
dev-dependencies = []
```

No change needed — `uv run shiny run app.py` already works.

- [ ] **Step 2: Verify command works**

Run: `uv run shiny run app.py --help`
Expected: Shiny help output (no errors).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "docs: confirm uv run command for dashboard"
```

---

## Summary of Tasks

| Task | What | Files |
|------|------|-------|
| 1 | Create `app.py` with full Shiny app | Create `app.py` |
| 2 | Manual test: run app, verify UI | No files |
| 3 | Verify `uv run shiny run app.py` works | No files |
