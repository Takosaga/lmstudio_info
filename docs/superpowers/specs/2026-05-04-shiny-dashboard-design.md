# LMStudio Token Usage Dashboard Design

## Overview

A single-page Shiny dashboard that visualizes LMStudio token usage data from a local SQLite database. The dashboard shows a stacked bar chart of token usage by model over time, with summary cards for total tokens and average monthly usage.

## Architecture

- **Runtime**: Local-only, launched via `uv run shiny run app.py`
- **Framework**: Shiny (Python) + Plotly
- **Data source**: `data/lmstudio_usage.db` (SQLite)
- **Data layer**: Reuses `data_loader.load_usage_data()` and `lmstudio_db` modules
- **Single file**: `app.py` contains the entire app

## Components

### 1. Header
- Title: "LMStudio Token Usage"

### 2. Summary Cards (row)
- **Total Tokens** — sum of all token counts from the database
- **Average Monthly Tokens** — total tokens divided by number of distinct months in the data

### 3. Controls
- **Granularity toggle** — dropdown: "Daily" / "Monthly"
- **Model filter** — dropdown: "All models" + list of unique models from the data

### 4. Stacked Bar Chart
- **x-axis**: time (day or month, based on granularity selection)
- **y-axis**: token count (summed per time period)
- **color**: model name (one segment per model per bar)
- **palette**: auto (Plotly default)
- **interactive**: hover shows model name, token count, and date

## Data Flow

1. App starts → reads `data/lmstudio_usage.db` via `load_usage_data()`
2. Reactive values compute: total tokens, average monthly tokens, unique models, time-aggregated data
3. User selects granularity → reactive filter recalculates time periods
4. User selects model filter → chart re-renders with filtered data
5. Plotly renders stacked bar chart from aggregated data

## Error Handling

- **Missing DB file**: Show a card saying "Database not found at data/lmstudio_usage.db. Run the data import first."
- **Empty data**: Show a card saying "No data available."
- **Database query error**: Catch and display as a card with the error message

## Dependencies

Already in `pyproject.toml`:
- `shiny>=1.6.0`
- `plotly>=6.7.0`
- `pandas>=2.0.0`

No new dependencies required.

## Running the App

```bash
uv run shiny run app.py
```
