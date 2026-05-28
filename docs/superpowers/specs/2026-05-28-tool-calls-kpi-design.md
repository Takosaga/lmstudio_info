# Total Tool Calls KPI Card Design

## Overview

Add a 4th KPI card to the Shiny dashboard showing the total tool call count for the selected time period, respecting the same filters (time range, source) as existing KPI cards.

## Changes

### UI (`app.py`)

- Add a 4th `ui.card` to the existing KPI row with:
  - `output_text_verbatim("total_tool_calls_header")` displaying "Total Tool Calls"
  - `output_text_verbatim("total_tool_calls")` showing the formatted count
- Change all four columns from `ui.column(4, ...)` to `ui.column(3, ...)` so they fit evenly in a 12-column grid

### Server (`app.py`)

Add two reactive outputs following the existing pattern:

```python
@output
@render.text
def total_tool_calls_header():
    return "Total Tool Calls"

@output
@render.text
def total_tool_calls():
    data = filtered_data()
    if data is None or data.empty:
        return "No data available."
    total = int(data["tool_call_count"].sum())
    return f"{total:,}"
```

## Data

Uses the existing `tool_call_count` column in the `conversations` table. No database schema changes required.
