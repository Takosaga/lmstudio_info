# Chart: Filter Models by Token Usage Threshold

**Date:** 2026-07-06  
**Author:** AI Agent (brainstorming skill)  
**Status:** Implemented

## Summary

Change the model-based stacked bar chart in the LMStudio usage dashboard to display only models that have used more than 10M tokens in the selected period, with a fallback to showing the top 5 models if none exceed the threshold.

## Decisions

### Threshold and Fallback
- **Threshold:** 10,000,000 tokens
- **Fallback:** If no models reach the threshold, show top 5 models by usage

### Implementation Scope
- Only affects the model-based stacked bar chart (`usage_chart` output)
- Does not affect token-type breakdown or KPI cards

## Approach Selection

Three approaches were considered:
1. **Simple threshold filter with fallback** (selected)
2. Dynamic threshold with visual indicator
3. Threshold + proportional view

**Selected:** Approach 1 — Minimal code change, preserves fallback behavior, aligns with user intent.

## Implementation Details

### Modified File
- `app.py` → `usage_chart()` output function

### Key Changes
```python
# Compute model totals from full filtered period (before any filtering)
model_totals = data.groupby("model")["token_count"].sum()

# Filter by 10M token threshold, fallback to top 5 if none
displayed_models = model_totals[model_totals >= 10_000_000].index.tolist()
if not displayed_models:
    displayed_models = model_totals.nlargest(5).index.tolist()

# Filter data to only selected models for both branches
agg_top5 = data[data["model"].isin(displayed_models)].copy()
```

### Edge Cases
- **Empty data:** Returns `None` as before
- **Zero models pass threshold:** Falls back to top 5
- **Some models above threshold:** Only shows those above threshold

## Testing
- No automated tests added (trivial change, YAGNI)
- Manual verification: run dashboard and confirm chart shows correct models

## References
- Brainstorming session: clarifying questions on scope and empty state behavior
- Ponytail mode: lazy solution with minimal changes
