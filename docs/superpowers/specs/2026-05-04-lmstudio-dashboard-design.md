# Interactive LMStudio Token Usage Dashboard Design

## Overview

Refresh the existing Shiny dashboard (`app.py`) to render the stacked bar chart interactively in the browser instead of as a saved PNG file. This enables hover tooltips, zoom, and pan without file I/O overhead.

## Current State

- `app.py` uses `@render.image` + `fig.write_image()` to save the Plotly chart as `static/chart.png` and serve it as a static image.
- KPI cards show Total Tokens and Average Monthly Tokens.
- Controls: granularity selector (Daily/Monthly) and model filter dropdown.
- Top 5 models are computed dynamically by total token count.

## Changes

### 1. Interactive Chart Rendering

- Replace `ui.output_plot("usage_chart")` with `ui.output_plotly("usage_chart")`.
- Replace `@render.image` with `@render.plotly`.
- Return the Plotly figure object directly instead of writing to disk.
- Remove `fig.write_image()` and the `static/chart.png` file.

### 2. Enhanced Hover Tooltips

Each bar segment tooltip displays:
- Model name
- Token count (formatted with commas)
- Percentage of that time period's total

### 3. Improved Styling

- Use a distinct color palette (`plotly.colors.qualitative.Set3`) with explicit colors.
- Show token count labels inside bars where space allows.
- Remove unnecessary grid lines for cleaner look.
- Wider chart area with better margins.

### 4. New KPI Card: Top Model

Add a third card showing the top model by total token count (e.g., "qwen/qwen3.5-9b").

### 5. KPI Card Layout

Three equal-width cards in a row:
- Total Tokens
- Average Monthly Tokens
- Top Model

## Data Flow

```
Database (data/lmstudio_usage.db)
    → load_usage_data() → pandas DataFrame (module-level)
    → filter by model/granularity (reactive)
    → compute top 5 models
    → aggregate by time × model
    → Plotly figure → render.plotly → browser
```

## Scope

Single file change (`app.py`). No new dependencies. No new files.
