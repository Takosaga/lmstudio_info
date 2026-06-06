# Remove Source Selector & Filter Token Type to Input/Output Only

## Problem

The dashboard shows a "Source" filter (LMStudio / OpenCode / Pi / All) that the user no longer needs — they always want all sources combined. Additionally, when breaking down by token type, all four types (Input, Output, Reasoning, Cache Read) are shown; the user wants only Input and Output.

## Changes

### 1. Remove Source Selector from UI
- Delete `ui.input_radio_buttons("source_filter", ...)` from `app_ui` sidebar in `app.py`
- Sidebar now has three controls: Time Period, Breakdown by, Time Range

### 2. Remove Source Filtering Logic
- In `filtered_data()` server function, remove the source filter block:
  ```python
  src = input.source_filter()
  if src and src != "all":
      data = data[data["source"] == src]
  ```
- All downstream computations (KPI cards, charts) always use all three sources

### 3. Filter Token Type Chart to Input + Output Only
- In the `token_type` breakdown branch of `usage_chart()`:
  - `token_cols` → `['input_tokens', 'output_tokens']`
  - Mapped names → `'Input Tokens'`, `'Output Tokens'`
  - Palette → `['#457b9d', '#e63946']` (2 colors)
- KPI cards (`total_tokens`, `avg_value`, `top_model`) remain unchanged — they still sum all token types

### 4. Calendar Heatmap
- No changes — already uses all sources and total tokens across all types

## Scope

Single file: `app.py`. No database, data loader, or other module changes required.
