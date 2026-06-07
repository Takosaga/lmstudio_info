# Token Type Chart — Logarithmic Y-axis

**Date**: 2026-06-07
**Status**: Approved
**App**: LMStudio Token Usage Dashboard (Shiny + Plotly)

## Problem

When the user selects "Token Type" breakdown, input tokens (~311M total) dwarf output tokens (~3M total, ~1% of input). On a linear-scale stacked bar chart, output token bars are nearly invisible — often 1–2 pixels tall or completely clipped.

## Solution

Apply a logarithmic y-axis scale **only** to the token-type breakdown chart. The model-based chart remains linear since model token counts are typically within an order of magnitude of each other.

## Design Details

### Scope
- Only affects the `usage_chart` output when `input.breakdown_by() == "token_type"`.
- The model-based branch is unchanged.

### Implementation
In the `usage_chart` server function, in the token-type branch (after the `px.bar()` call and before `fig.update_layout()`), add:

```python
fig.update_layout(
    yaxis=dict(type='log'),
)
```

This single line switches the y-axis to logarithmic scale. Plotly handles zero values by clipping them to a small positive floor internally.

### Axis Label
Change the y-axis label from `"Total Tokens"` to `"Total Tokens (log scale)"` in the `labels` dict passed to `px.bar()`, so users understand they're looking at a log-scaled axis.

### Tooltips / Hover
Unchanged. Hover tooltips display raw token counts via `custom_data` (`%{customdata[1]:,}`), so values shown are absolute and not distorted by the scale.

### Zero Handling
- Plotly's log scale automatically clips zero/negative y-values to a small positive floor (typically 1).
- No additional guard code needed — the existing `fillna(0)` on token columns means any period with no output tokens will show a zero-height bar, which Plotly renders as invisible (correct behavior: no data to show).

### Visual Preview
```
Before (linear):                         After (log scale):
  |███████████████░░|                      |███████████████|
  |                  |                      |████|
  |                  |    output ~1px       |████|   output clearly visible
  +------------------+                      +------------------
```

## Files Changed
- `app.py` — `usage_chart` server function, token-type branch:
  - Add `yaxis=dict(type='log')` to `fig.update_layout()` call.
  - Update y-axis label in `labels` dict.

## Out of Scope
- No changes to the model-based chart.
- No changes to the calendar heatmap.
- No changes to KPI cards or other dashboard elements.
- No changes to data loading or database logic.
