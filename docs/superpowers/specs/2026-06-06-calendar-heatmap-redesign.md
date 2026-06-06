# Calendar Heatmap Redesign

## Problem

The calendar heatmap in the LMStudio dashboard shows a variable-width date range (from first data point to last), resulting in an inconsistent display. Users expect a full GitHub-style contribution graph showing exactly one year of data.

## Goal

Replace the variable-width calendar with a fixed 52-week view that always ends on the most recent data day, and show the actual calendar date on hover instead of just the month abbreviation and day name.

## Design

### Date Range

**Before**: `pd.date_range(start=min_date, end=max_date)` — width depends on data availability.

**After**: Compute `last_date = daily['_date'].max()`, then `start_date = last_date - pd.Timedelta(days=364)`. The matrix always covers exactly 52 weeks (365 days). Dates before the first data point show as zero (blank squares).

### Hover Tooltip

**Before**: `hovertemplate` shows month abbreviation (`%{x}`) and day name (`%{y}`).

**After**: Build a `dates` matrix matching the `z` matrix shape, where each cell contains a formatted date string (e.g., `"Jun 6, 2026"`). Pass via `customdata` and update hovertemplate to display it.

### No Selection / Layout

No changes. The current Heatmap has no selection mechanism. Layout parameters (height=250, tickangle=-15, month labels on top) remain unchanged.

## Files Changed

| File | Change |
|------|--------|
| `app.py` → `_build_calendar_data()` | Replace date range with trailing 52 weeks; add `dates` matrix; return in dict |
| `app.py` → `usage_chart()` | Update hovertemplate to use `customdata[0]` for date display |

## Scope

Single focused change: calendar heatmap rendering only. No new files, no new modules. ~10 lines across 2 locations in `app.py`.
