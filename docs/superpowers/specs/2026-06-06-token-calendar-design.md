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
- **Color scale**: 5-level blue gradient from light gray (`#ebedf0`) for zero tokens to dark blue (`#0e4429`) for highest token count, matching GitHub's contribution palette.
- **Hover tooltip**: Model name, date, and total token count with comma formatting.
- **Time span**: Exactly 365 days from the most recent `user_last_message_at` in the dataset.

## Integration

- New "Calendar" radio button in the existing sidebar of `app.py`, alongside "Monthly" and "Daily" choices.
- When selected, replaces the main chart area with the heatmap instead of the stacked bar chart.
- Uses `shinywidgets.render_plotly()` consistent with the existing `usage_chart`.
- Reuses the same data loading pipeline (`_load_all_sources()`) — no new DB queries.
