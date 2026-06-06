# GitHub-Style Calendar Heatmap Design

## Goal

Replace the current calendar heatmap with a GitHub-contributions-style view: single aggregated heatmap where columns represent weeks (labeled by month) and rows represent days of the week. The calendar becomes the default selection in the "Time Period" selector. Other filters (breakdown by, time range) are hidden when Calendar is active; only the source filter remains visible.

## Design Decisions

### Default Selection
- `time_period` default changes from `"Monthly"` to `"Calendar"`.

### Filter Visibility
- When `Calendar` is selected: hide `breakdown_by` and `time_range` radio buttons via `ui.update_radio_buttons`.
- `source_filter` remains visible so the user can still choose LMStudio / OpenCode / Both.
- When `Daily` or `Monthly` is selected, all three filters are visible as they currently are.

### Calendar Data Aggregation
- Aggregate **all models** into a single daily token count per date (input + output + reasoning + cache_read).
- Reshape into a 7-row × N-column matrix: rows = days of week (Sun–Sat), columns = weeks.
- Zero-fill any missing dates so every cell exists in the grid.

### Calendar Rendering
- Use `go.Heatmap` with the 7×N matrix.
- **X-axis**: Week numbers as tick labels; month name label on the first column of each new month, empty string for other weeks.
- **Y-axis**: `['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']`.
- **Color scale**: GitHub green palette (`#ebedf0` → `#b6e2b4` → `#9be9a8` → `#40c463` → `#30a14e` → `#216e39`).
- **Hover template**: `<b>%{x}</b><br>Date: %{y}<br>Tokens: %{z:,}`.
- **Height**: Fixed at ~250px with sufficient margin (l=80, r=30, t=40, b=60).

### Daily / Monthly Modes
- Unchanged from current behavior. Bar charts render as before when the user selects Daily or Monthly.

## Changes to `app.py`

1. **`_build_calendar_data` rewrite**: Replace model×date pivot with daily aggregation → 7-row day-of-week × week matrix. Return dict with `z`, `x` (week labels), `y` (day names).
2. **`usage_chart` calendar branch**: Update to use new data format and GitHub-style layout.
3. **Filter visibility effect**: Add a `@reactive.effect` that calls `ui.update_radio_buttons` with empty choices for hidden filters when Calendar is selected, restoring original choices when Daily/Monthly is selected.
4. **Default selection**: Change `selected="Monthly"` to `selected="Calendar"` in the `time_period` radio button.

## No Changes Required
- `data_loader.py`, `lmstudio_db.py`, `lmstudio_tokens.py`, `opencode_db.py`: No changes needed; calendar uses the same unified data pipeline.
- Existing tests for `_build_calendar_data`: Will need updating to reflect new return format (7-row matrix instead of model×date pivot).
