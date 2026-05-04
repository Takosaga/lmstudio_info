# LMStudio Dashboard Sidebar Layout Design

## Overview

Refactor the LMStudio Token Usage Dashboard from a `page_fluid` layout to a `page_sidebar` layout with three controls in the sidebar and centered KPI cards in the main content.

## Architecture

- **Runtime**: Local-only, launched via `uv run shiny run app.py`
- **Framework**: Shiny (Python) + Plotly
- **Data source**: `data/lmstudio_usage.db` (SQLite)
- **Data layer**: Reuses `data_loader.load_usage_data()` and `lmstudio_db` modules
- **Single file**: `app.py` contains the entire app

## Layout

```
┌────────────┬──────────────────────────────────────────┐
│  SIDEBAR   │           MAIN CONTENT                   │
│            │                                          │
│ Time Period│  [   Centered KPI Cards Row   ]         │
│ (dropdown) │  ┌──────────┐ ┌──────────┐ ┌──────────┐│
│            │  │Total     │ │Average   │ │Top       ││
│ Model      │  │Tokens    │ │Monthly   │ │Model     ││
│ (dropdown) │  │          │ │Tokens    │ │          ││
│            │  └──────────┘ └──────────┘ └──────────┘│
│ Time Range │                                          │
│ (radio btns)│                                         │
│            │  ┌──────────────────────────────────┐   │
│            │  │  Token Usage Over Time Chart     │   │
│            │  │  [Stacked bar chart]             │   │
│            │  └──────────────────────────────────┘   │
└────────────┴──────────────────────────────────────────┘
```

## Components

### 1. Sidebar Controls

**Time Period** (dropdown)
- Choices: "Daily" / "Monthly"
- Replaces "Granularity" label

**Model** (dropdown)
- Default: "Top 5 Models"
- Additional options: all individual model names from the data
- When "Top 5 Models" is selected: chart shows top 5 models by total token count
- When a specific model is selected: chart shows only that model

**Time Range** (inline radio buttons)
- Presets: "7 days" | "30 days" | "90 days" | "Current Year" | "All Time"
- Filters data by `created_at` timestamp range
- Default: "All Time"

### 2. KPI Cards (centered row)

Three cards in a centered row, all using consistent `output_text_verbatim` body text:

- **Total Tokens** — sum of all token counts, formatted with commas
- **Average Monthly Tokens** — total tokens divided by distinct months, formatted with commas
- **Top Model** — most-used model name and its token count, formatted with commas

### 3. Chart

- Stacked bar chart of token usage over time
- x-axis: time period (day or month, based on Time Period selection)
- y-axis: token count
- color: model name
- Palette: 5 distinct colors (matches top 5 models)
- Hover tooltip: model name, token count, period share percentage
- Legend: horizontal above chart
- Title: "Token Usage Over Time"

## Data Flow

1. App starts → reads `data/lmstudio_usage.db` via `load_usage_data()`
2. Reactive values compute: total tokens, average monthly tokens, unique models, time-aggregated data
3. User selects Time Period → reactive filter recalculates time periods
4. User selects Model → chart re-renders with filtered data (top 5 or single model)
5. User selects Time Range → all reactive values recalculate with date-filtered data
6. Plotly renders stacked bar chart from aggregated data

## Error Handling

- **Missing DB file**: Show "No data available." in all KPI cards and chart
- **Empty data after filter**: Show "No data available." in affected components
- **Database query error**: Catch and display as a card with the error message

## Dependencies

Already in `pyproject.toml`:
- `shiny>=1.6.0`
- `plotly>=6.7.0`
- `pandas>=2.0.0`
- `shinywidgets>=0.8.0`

No new dependencies required.

## Running the App

```bash
uv run shiny run app.py
```
