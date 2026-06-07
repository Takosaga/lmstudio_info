# Calendar Percentile-Based Color Scaling

## Problem

The calendar heatmap in `app.py` uses fixed token thresholds capped at 100k. With daily usage ranging from ~1m to 50m tokens, every active day renders as the darkest green (#216e39), eliminating all visual differentiation.

## Current Implementation

`_build_calendar_figure()` computes colors via:

```python
pct = np.minimum(z / 100_000, 1.0)
colors = np.select(
    [z == 0, pct < 0.05, pct < 0.15, pct < 0.30, pct < 0.50, pct < 0.75],
    ['#ebedf0', '#b6e2b4', '#9be9a8', '#40c463', '#30a14e', '#2ea44f'],
    default='#216e39'
)
```

Thresholds are static: 5k, 15k, 30k, 50k, 75k — all far below actual data.

## Design

Replace fixed thresholds with percentile-based thresholds computed from the actual non-zero data at render time.

### Algorithm

1. Extract non-zero token counts from the calendar matrix (`z[z > 0]`).
2. Compute percentiles: p10, p25, p50, p75, p90 from the non-zero values.
3. Map each cell to a color bucket using these dynamic thresholds:

| Bucket | Condition | Color | Meaning |
|--------|-----------|-------|---------|
| 0 | `z == 0` | `#ebedf0` | No data |
| 1 | `z < p10` | `#b6e2b4` | Lowest 10% of active days |
| 2 | `z < p25` | `#9be9a8` | 10–25th percentile |
| 3 | `z < p50` | `#40c463` | 25–50th percentile |
| 4 | `z < p75` | `#30a14e` | 50–75th percentile |
| 5 | `z < p90` | `#2ea44f` | 75–90th percentile |
| 6 | `z >= p90` | `#216e39` | Top 10% of active days |

### Edge Cases

- **No non-zero data:** All thresholds set to 0; all cells render as lightest green.
- **Few data points (<5):** Percentiles may coincide; colors still render correctly but buckets compress. This is acceptable — the calendar needs sufficient data for meaningful differentiation anyway.
- **Single active day:** p10 = p25 = ... = p90 = that value; all non-zero cells get darkest green. Correct behavior.

### Implementation Location

File: `app.py`, function `_build_calendar_figure()`, lines ~110–120 (color computation block).

No changes to UI, data loading, or other functions required. Self-contained change.

### Files Modified

- `app.py` — only file changed. ~10 lines modified in `_build_calendar_figure()`.
