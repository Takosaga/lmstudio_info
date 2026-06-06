# LMStudio Dashboard Redesign — Design Spec

**Date:** 2026-06-06
**Status:** Approved
**File:** `app.py` (UI layout + minor text change)

## Problem

The calendar heatmap is tied to the "Time Period" sidebar selector. It hides when Monthly or Daily is selected, making it impossible to have a constant year-over-year overview alongside filtered bar charts.

## Solution

Separate the calendar from the Time Period selector. The calendar always displays at the top of the dashboard (52 weeks from last data entry). The Time Period selector controls only the bar chart below the KPI cards.

## UI Layout

```
┌─────────────────────────────────────────────┐
│  Calendar Heatmap — always visible          │
│  Always shows 52 weeks from last data entry │
│  Responds to Source filter only             │
└─────────────────────────────────────────────┘
┌──────┬──────┬──────┬──────┐
│Total │Avg   │Top   │Tool  │
│Tokens│Daily │Model │Calls │
└──────┴──────┴──────┴──────┘
┌─────────────────────────────────────────────┐
│  Bar Chart — Monthly or Daily               │
│  Controlled by sidebar filters              │
└─────────────────────────────────────────────┘
```

## Component Changes

### `app.py`

1. **New reactive calc: `_calendar_data()`**
   - Calls existing `filtered_data()` to get source-filtered data
   - Passes result to existing `_build_calendar_data()`
   - Always returns 52 weeks from last data point
   - Independent of `time_period` and `time_range` inputs

2. **New output: `calendar_chart`**
   - Renders the heatmap at the top of the page using `_build_calendar_figure()` helper
   - Placed in `app_ui` before KPI row

3. **Extract calendar figure builder** — move the Plotly figure-building logic currently inline in `usage_chart()` (under `if input.time_period() == "Calendar"`) into a new standalone helper `_build_calendar_figure(cal_data)` that returns a `go.Figure`. This avoids code duplication since the calendar output will call this same helper.

5. **Sidebar update: `time_period`**
   - Before: `{"Monthly": "Monthly", "Daily": "Daily", "Calendar": "Calendar"}`
   - After: `{"Monthly": "Monthly", "Daily": "Daily"}`
   - Default remains `"Monthly"`

6. **UI reordering in `app_ui`**
   - Sidebar (unchanged except time_period choices)
   - Calendar chart output (new, top)
   - KPI cards row (moved below calendar)
   - Bar chart card (stays at bottom, no longer switches to calendar)

### No changes to:
- `data_loader.py` — data loading unchanged
- `lmstudio_db.py` — DB operations unchanged
- `lmstudio_tokens.py` — conversation scanning unchanged
- `opencode_db.py` — OpenCode sync unchanged
- `assets/styles.css` — existing flexbox centering already handles KPI card centering
- Tests — no new behavior to test

## Data Flow

```
filtered_data() ──┬──→ calendar_data() ──→ _build_calendar_data() ──→ calendar_chart
                  │
                  ├──→ total_tokens output
                  ├──→ avg_value output
                  ├──→ top_model output (one-line format)
                  ├──→ total_tool_calls output
                  │
                  └──→ usage_chart (bar chart only, Monthly/Daily)
```

`filtered_data()` applies source filter + time range filter. Calendar data inherits the source filter but ignores time range (always shows full 52 weeks).

## Error Handling

No new error paths. The existing calendar rendering already handles `None`/empty data by returning `None` from the Plotly output (shows nothing). All existing try/except blocks in `_load_all_sources()` are preserved.

## Files Modified

- `app.py` — UI reordering, new calendar output, sidebar update, top_model format change
