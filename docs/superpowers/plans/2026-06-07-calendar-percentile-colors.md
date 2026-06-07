# Calendar Percentile-Based Color Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed token thresholds in the calendar heatmap with percentile-based thresholds so color differentiation works across any data range.

**Architecture:** Extract the color-computation logic from `_build_calendar_figure()` into a standalone helper function `_compute_calendar_colors(z)`, then wire it back in. This makes the logic testable without needing Plotly or full figure construction.

**Tech Stack:** Python, NumPy, pytest — same as existing project.

---

## Task 1: Add tests for percentile color computation

**Files:**
- Create: `tests/test_calendar_colors.py`
- Modify: `app.py` (later tasks)

- [ ] **Step 1: Write test file with failing imports**

Create `tests/test_calendar_colors.py`:

```python
"""Tests for calendar heatmap color computation."""
import numpy as np
import pytest


class TestComputeCalendarColors:
    """Test _compute_calendar_colors percentile-based coloring."""

    def test_all_zeros(self):
        """All-zero matrix should produce lightest gray for every cell."""
        from app import _compute_calendar_colors
        z = np.zeros((7, 8), dtype=int)
        colors = _compute_calendar_colors(z)
        expected = ['#ebedf0'] * 56
        assert list(colors.flatten()) == expected

    def test_uniform_nonzero(self):
        """All identical non-zero values should all get darkest green."""
        from app import _compute_calendar_colors
        z = np.full((7, 8), 1_000_000, dtype=int)
        colors = _compute_calendar_colors(z)
        # With a single unique value, p10=p25=...=p90=value, so all >= p90
        expected = ['#216e39'] * 56
        assert list(colors.flatten()) == expected

    def test_two_values(self):
        """Two distinct values should split into two color buckets."""
        from app import _compute_calendar_colors
        z = np.zeros((7, 8), dtype=int)
        # Fill first 20 cells with low value, next 20 with high value
        z_flat = z.flatten()
        for i in range(20):
            z_flat[i] = 1_000_000   # low
        for i in range(20, 40):
            z_flat[i] = 50_000_000  # high
        colors = _compute_calendar_colors(z)
        # Low values should be lighter than high values
        low_colors = set(colors.flatten()[:20])
        high_colors = set(colors.flatten()[20:40])
        assert len(low_colors) > 0
        assert len(high_colors) > 0
        # The darkest color (#216e39) should appear in high bucket
        assert '#216e39' in high_colors or list(high_colors)[0] != list(low_colors)[0]

    def test_five_buckets_populated(self):
        """Wide data range should populate all 5 non-zero color buckets."""
        from app import _compute_calendar_colors
        z = np.zeros((7, 8), dtype=int)
        z_flat = z.flatten()
        # Distribute values across 5 percentiles
        values = [2_000_000, 10_000_000, 20_000_000, 30_000_000, 48_000_000]
        for i, v in enumerate(values):
            start = i * 10
            end = (i + 1) * 10
            z_flat[start:end] = v
        colors = _compute_calendar_colors(z)
        non_gray = set(c for c in colors.flatten() if c != '#ebedf0')
        assert len(non_gray) == 5, f"Expected 5 distinct green shades, got {len(non_gray)}: {non_gray}"

    def test_single_active_day(self):
        """One active day should get darkest green; rest gray."""
        from app import _compute_calendar_colors
        z = np.zeros((7, 8), dtype=int)
        z[0, 0] = 5_000_000
        colors = _compute_calendar_colors(z)
        assert colors[0, 0] == '#216e39'
        assert all(c == '#ebedf0' for r in colors for c in r if not (r is colors[0] and c is colors[0, 0]))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/takosaga/Projects/lmstudio_info && python -m pytest tests/test_calendar_colors.py -v`

Expected: FAIL with `ImportError` — `_compute_calendar_colors` does not exist yet.

- [ ] **Step 3: Commit test file**

```bash
cd /home/takosaga/Projects/lmstudio_info
git add tests/test_calendar_colors.py
git commit -m "test: add percentile color computation tests"
```

---

## Task 2: Implement `_compute_calendar_colors` helper function

**Files:**
- Modify: `app.py:95-105` (the color computation block in `_build_calendar_figure`)

- [ ] **Step 1: Add the helper function to app.py**

Insert this function **before** `_build_calendar_figure()` (around line 94):

```python
def _compute_calendar_colors(z: np.ndarray) -> np.ndarray:
    """Compute GitHub-style green colors from a token-count matrix using percentile thresholds.

    Args:
        z: 2D numpy array of token counts (7 rows x N columns).

    Returns:
        2D numpy array of the same shape with hex color strings.
    """
    palette = ['#ebedf0', '#b6e2b4', '#9be9a8', '#40c463', '#30a14e', '#2ea44f', '#216e39']

    # Flatten to 1D for percentile computation
    flat = z.flatten()
    non_zero = flat[flat > 0]

    if len(non_zero) == 0:
        return np.full(z.shape, palette[0], dtype=object)

    p10, p25, p50, p75, p90 = np.percentile(non_zero, [10, 25, 50, 75, 90])

    colors = np.select(
        [flat == 0, flat < p10, flat < p25, flat < p50, flat < p75, flat < p90],
        [palette[0], palette[1], palette[2], palette[3], palette[4], palette[5]],
        default=palette[6],
    )
    return colors.reshape(z.shape)
```

- [ ] **Step 2: Replace the color computation in `_build_calendar_figure()`**

Replace lines ~110–117 in `_build_calendar_figure()`:

```python
# OLD (lines to replace):
    # Vectorized color computation via numpy (replaces Python if/else loop)
    z = np.array(cal_data['z'])
    pct = np.minimum(z / 100_000, 1.0)
    colors = np.select(
        [z == 0, pct < 0.05, pct < 0.15, pct < 0.30, pct < 0.50, pct < 0.75],
        ['#ebedf0', '#b6e2b4', '#9be9a8', '#40c463', '#30a14e', '#2ea44f'],
        default='#216e39'
    )
```

With:

```python
# NEW:
    # Vectorized color computation via percentile-based thresholds
    z = np.array(cal_data['z'])
    colors = _compute_calendar_colors(z)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd /home/takosaga/Projects/lmstudio_info && python -m pytest tests/test_calendar_colors.py -v`

Expected: All 5 tests PASS.

- [ ] **Step 4: Commit**

```bash
cd /home/takosaga/Projects/lmstudio_info
git add app.py tests/test_calendar_colors.py
git commit -m "feat: percentile-based calendar heatmap color scaling"
```

---

## Task 3: Manual verification

- [ ] **Step 1: Run the app and verify visually**

Run: `cd /home/takosaga/Projects/lmstudio_info && python app.py`

Expected: App starts on http://127.0.0.1:3000. Calendar heatmap should show multiple green shades (light to dark) instead of all darkest green. Hover over different days to see token counts and confirm color matches usage level.

- [ ] **Step 2: Commit verification**

No commit needed — this is manual QA only. If issues found, fix and amend the commit from Task 2.

---

## Self-Review Checklist

1. **Spec coverage:** Each spec requirement covered — dynamic percentile thresholds (Task 2), all 6 buckets preserved (Task 2), edge cases handled in helper function (zero data, single value, few data points).
2. **Placeholder scan:** No TBD/TODO/fill-in patterns found. All code is concrete.
3. **Type consistency:** `np.ndarray` input → `np.ndarray` output, same shape as input z. Palette list matches original 7 colors exactly.
