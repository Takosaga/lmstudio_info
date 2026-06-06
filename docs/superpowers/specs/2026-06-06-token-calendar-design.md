# Token Calendar Design

## Overview

Add a GitHub-style contribution calendar to the Shiny dashboard, showing token usage per model per day over the last 365 days. Color intensity reflects total tokens (input + output + reasoning + cache).

## Data Aggregation

For each day in the last 365 days from the most recent conversation:
- Sum all token columns (`input_tokens`, `output_tokens`, `reasoning_tokens`, `cache_read_tokens`) into a single `total_tokens` value per conversation.
- Group by `(date, model)` and sum `total_tokens`.
- Pivot into a matrix of `[model × date]` where missing cells are zero.
- Only include models that have activity within the 365-day window.
- Sort rows by total token usage (descending).

## Visualization

- **Chart type**: Plotly heatmap (`go.Heatmap`).
- **X-axis**: Days of the year, labeled by week boundaries.
- **Y-axis**: Models sorted by total usage (descending).
- **Color scale**: Blue gradient from light gray (`#f0f0f0`) for zero to dark blue (`#1a4d8c`) for highest token count.
- **Hover tooltip**: Model name, date, and total token count with comma formatting.
- **Time span**: Exactly 365 days from the most recent `user_last_message_at` in the dataset.

## Integration

- New "Calendar" tab in the existing Shiny app (`app.py`).
- Added as a new radio button choice under `time_period` or as a separate sidebar control.
- Uses `shinywidgets.render_plotly()` consistent with the existing `usage_chart`.
- Reuses the same data loading pipeline (`_load_all_sources()`) — no new DB queries.
