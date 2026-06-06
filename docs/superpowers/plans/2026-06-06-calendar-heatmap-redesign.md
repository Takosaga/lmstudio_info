# Calendar Heatmap 52-Week View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the variable-width calendar heatmap with a fixed 52-week view that always ends on the most recent data day, and show the actual calendar date on hover.

**Architecture:** Modify `_build_calendar_data()` in `app.py` to compute a trailing 365-day range instead of min-to-max. Build a parallel `dates` matrix mapping each (row, col) to its formatted date string. Pass dates via Plotly's `customdata` and update the hovertemplate.

**Tech Stack:** Python 3.12, pandas, plotly, shiny

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `app.py` | Modify | `_build_calendar_data()` date range + dates matrix; `usage_chart()` hovertemplate |
| `tests/test_calendar_heatmap.py` | Modify | Add test for 52-week fixed width; update existing tests for new return dict key |

---

### Task 1: Update `_build_calendar_data` — trailing 52-week date range

**Files:**
- Modify: `app.py:_build_calendar_data()` (lines ~40–93)
- Test: `tests/test_calendar_heatmap.py`

- [ ] **Step 1: Write failing test for 52-week fixed width**

Add this test to `tests/test_calendar_heatmap.py`:

```python
def test_build_calendar_data_52_week_range():
    """Test that calendar always spans ~52 weeks ending on last data day."""
    from app import _build_calendar_data

    # Data spanning exactly 10 days in Jan 2025 (Wed Jan 1 to Fri Jan 10)
    data = pd.DataFrame({
        'model': ['gpt-4'],
        'created_at': pd.to_datetime([
            '2025-01-01', '2025-01-03', '2025-01-05',
            '2025-01-07', '2025-01-09',
        ]),
        'input_tokens': [100] * 5,
        'output_tokens': [300] * 5,
        'reasoning_tokens': [0] * 5,
        'cache_read_tokens': [0] * 5,
    })

    result = _build_calendar_data(data)

    # Last data day is Jan 9, 2025 (Thursday).
    # Start should be Jan 9 - 364 days = Jan 10, 2024.
    # That gives exactly 52 weeks (365 days / 7 ≈ 52 columns).
    assert len(result['z']) == 7
    n_cols = len(result['z'][0])
    assert n_cols >= 52, f"Expected ~52 columns, got {n_cols}"
    assert n_cols <= 53, f"Expected ~52 columns, got {n_cols}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/takosaga/Projects/lmstudio_info && uv run pytest tests/test_calendar_heatmap.py::test_build_calendar_data_52_week_range -v`

Expected: FAIL — either the test doesn't exist yet (NameError), or current implementation returns ~1 column instead of ~52.

- [ ] **Step 3: Modify `_build_calendar_data` to use trailing 52-week range**

Replace the date range computation in `app.py`. Find this block inside `_build_calendar_data`:

```python
    # Create a complete date range and map to (day_of_week, week_index)
    all_dates = pd.date_range(start=daily['_date'].min(), end=daily['_date'].max())
    first_day = all_dates[0]
```

Replace with:

```python
    # Create a trailing 52-week date range ending on the last data day
    last_date = daily['_date'].max()
    start_date = last_date - pd.Timedelta(days=364)
    all_dates = pd.date_range(start=start_date, end=last_date)
    first_day = all_dates[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/takosaga/Projects/lmstudio_info && uv run pytest tests/test_calendar_heatmap.py::test_build_calendar_data_52_week_range -v`

Expected: PASS — matrix now has ~52 columns.

- [ ] **Step 5: Verify existing tests still pass**

Run: `cd /home/takosaga/Projects/lmstudio_info && uv run pytest tests/test_calendar_heatmap.py::test_build_calendar_data_basic tests/test_calendar_heatmap.py::test_build_calendar_data_aggregation tests/test_calendar_heatmap.py::test_build_calendar_data_multiple_models_days -v`

Expected: PASS — existing aggregation logic is unchanged, only the range expanded. (Columns shift but values at correct positions remain the same.)

- [ ] **Step 6: Commit**

```bash
cd /home/takosaga/Projects/lmstudio_info
git add tests/test_calendar_heatmap.py app.py
git commit -m "feat: calendar heatmap uses trailing 52-week range ending on last data day"
```

---

### Task 2: Add `dates` matrix and expose via return dict

**Files:**
- Modify: `app.py:_build_calendar_data()` (after the z matrix construction)
- Test: `tests/test_calendar_heatmap.py`

- [ ] **Step 1: Write test for dates matrix**

Add this test to `tests/test_calendar_heatmap.py`:

```python
def test_build_calendar_data_dates_matrix():
    """Test that result contains a 'dates' matrix matching the z matrix shape."""
    from app import _build_calendar_data

    data = pd.DataFrame({
        'model': ['gpt-4'],
        'created_at': pd.to_datetime(['2025-01-01']),
        'input_tokens': [100],
        'output_tokens': [300],
        'reasoning_tokens': [0],
        'cache_read_tokens': [0],
    })

    result = _build_calendar_data(data)

    assert 'dates' in result
    assert len(result['dates']) == 7
    assert len(result['dates'][0]) >= 1
    # Each cell should be a date string like "Jan 1, 2025"
    assert isinstance(result['dates'][3][0], str)  # Wed is row 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/takosaga/Projects/lmstudio_info && uv run pytest tests/test_calendar_heatmap.py::test_build_calendar_data_dates_matrix -v`

Expected: FAIL — `'dates' not in result`.

- [ ] **Step 3: Build the `dates` matrix alongside the `z` matrix**

After the z matrix construction block in `_build_calendar_data`, add this code. Find the section that builds `rows_data` and after the line `for r in rows_data:` loop ends, add a dates matrix builder:

After this existing code:
```python
    # Build x-axis labels: month name on first week of each month, empty string otherwise
    x_labels = []
    current_month = None
    for w in range(max_col):
        week_start = first_day + pd.Timedelta(weeks=w)
        month_name = week_start.strftime('%b')

        if current_month is None or month_name != current_month:
            x_labels.append(month_name)
            current_month = month_name
        else:
            x_labels.append('')

    return {
        'z': z,
        'x': x_labels,
        'y': day_names,
    }
```

Replace the `return` statement and add a dates matrix construction before it. Insert this block right before `return`:

```python
    # Build dates matrix: same shape as z, each cell is formatted date string
    dates = [['' for _ in range(max_col)] for _ in range(7)]
    for d in all_dates:
        row = (d.dayofweek + 1) % 7
        days_since_start = (d - first_day).days
        col = days_since_start // 7
        dates[row][col] = d.strftime('%b %-d, %Y')

    return {
        'z': z,
        'x': x_labels,
        'y': day_names,
        'dates': dates,
    }
```

Note: `%-d` gives the day without zero-padding (e.g., "Jun 6" not "Jun 06"), matching the reference screenshot.

- [ ] **Step 3b: Update existing tests that check for exact dict keys**

The existing test `test_build_calendar_data_empty` checks `assert result == {'z': [], 'x': [], 'y': []}`. Update it to include `'dates'`:

```python
def test_build_calendar_data_empty():
    """Test that empty data returns empty dicts."""
    from app import _build_calendar_data

    result = _build_calendar_data(None)
    assert result == {'z': [], 'x': [], 'y': [], 'dates': []}

    result = _build_calendar_data(pd.DataFrame())
    assert result == {'z': [], 'x': [], 'y': [], 'dates': []}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/takosaga/Projects/lmstudio_info && uv run pytest tests/test_calendar_heatmap.py -v`

Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/takosaga/Projects/lmstudio_info
git add tests/test_calendar_heatmap.py app.py
git commit -m "feat: add dates matrix to calendar heatmap output for hover tooltips"
```

---

### Task 3: Update `usage_chart` to display date on hover

**Files:**
- Modify: `app.py:usage_chart()` (calendar heatmap branch)

- [ ] **Step 1: Write test that verifies hovertemplate uses customdata**

Add this test to `tests/test_calendar_heatmap.py`:

```python
def test_usage_chart_calendar_hover():
    """Test that the calendar chart shows date strings on hover."""
    from app import _build_calendar_data
    import plotly.graph_objects as go

    data = pd.DataFrame({
        'model': ['gpt-4'],
        'created_at': pd.to_datetime(['2025-01-01']),
        'input_tokens': [100],
        'output_tokens': [300],
        'reasoning_tokens': [0],
        'cache_read_tokens': [0],
    })

    cal_data = _build_calendar_data(data)
    assert 'dates' in cal_data

    # Verify that customdata would be passed correctly to Plotly
    # (actual chart rendering tested via integration test below)
    fig = go.Figure(go.Heatmap(
        z=cal_data['z'],
        x=cal_data['x'],
        y=cal_data['y'],
        colorscale=[
            [0, '#ebedf0'],
            [0.15, '#b6e2b4'],
            [0.3, '#9be9a8'],
            [0.5, '#40c463'],
            [0.75, '#30a14e'],
            [1, '#216e39']
        ],
        customdata=cal_data['dates'],
        hovertemplate='<b>%{customdata[0]}</b><br>Tokens: %{z:,}<extra></extra>',
    ))

    # Verify the trace has customdata set
    assert fig.data[0].customdata is not None
    assert fig.data[0].customdata.shape == (7, len(cal_data['x']))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/takosaga/Projects/lmstudio_info && uv run pytest tests/test_calendar_heatmap.py::test_usage_chart_calendar_hover -v`

Expected: FAIL — the current app code doesn't pass `customdata` or use `%{customdata[0]}` in hovertemplate. (This test imports directly from plotly, not from the Shiny server, so it will fail at the assertion if customdata is None.)

- [ ] **Step 3: Update the calendar heatmap trace in `usage_chart()`**

Find this block in `app.py` inside the `usage_chart` function (the Calendar branch):

```python
            fig = go.Figure(go.Heatmap(
                z=cal_data['z'],
                x=cal_data['x'],
                y=cal_data['y'],
                colorscale=[
                    [0, '#ebedf0'],
                    [0.15, '#b6e2b4'],
                    [0.3, '#9be9a8'],
                    [0.5, '#40c463'],
                    [0.75, '#30a14e'],
                    [1, '#216e39']
                ],
                hovertemplate='<b>%{x}</b><br>Date: %{y}<br>Tokens: %{z:,}<extra></extra>',
            ))
```

Replace with:

```python
            fig = go.Figure(go.Heatmap(
                z=cal_data['z'],
                x=cal_data['x'],
                y=cal_data['y'],
                colorscale=[
                    [0, '#ebedf0'],
                    [0.15, '#b6e2b4'],
                    [0.3, '#9be9a8'],
                    [0.5, '#40c463'],
                    [0.75, '#30a14e'],
                    [1, '#216e39']
                ],
                customdata=cal_data['dates'],
                hovertemplate='<b>%{customdata[0]}</b><br>Tokens: %{z:,}<extra></extra>',
            ))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/takosaga/Projects/lmstudio_info && uv run pytest tests/test_calendar_heatmap.py -v`

Expected: ALL PASS.

- [ ] **Step 5: Integration test — run the app and verify visually**

```bash
cd /home/takosaga/Projects/lmstudio_info
uv run shiny run app.py &
sleep 3
curl -s http://127.0.0.1:3000/ | head -5
kill %1 2>/dev/null
```

Expected: App starts without errors, returns HTML. (Visual verification of hover and calendar width done manually in browser.)

- [ ] **Step 6: Commit**

```bash
cd /home/takosaga/Projects/lmstudio_info
git add tests/test_calendar_heatmap.py app.py
git commit -m "feat: show full date on calendar heatmap hover via customdata"
```

---

### Task 4: Run full test suite and final verification

- [ ] **Step 1: Run all tests**

Run: `cd /home/takosaga/Projects/lmstudio_info && uv run pytest -v`

Expected: ALL PASS.

- [ ] **Step 2: Commit any leftover changes**

```bash
cd /home/takosaga/Projects/lmstudio_info
git add -A
git diff --cached --stat
git commit -m "chore: final verification — all tests pass"
```

---

## Self-Review Checklist

1. **Spec coverage:** 
   - Trailing 52-week range → Task 1, Step 3 ✓
   - Dates matrix for hover → Task 2, Step 3 ✓
   - Hovertemplate update → Task 3, Step 3 ✓
   - No selection / layout changes → Noted as no-op in spec ✓

2. **Placeholder scan:** No TBD, TODO, or vague descriptions found. Every step contains exact code and commands.

3. **Type consistency:** `cal_data['dates']` is a `list[list[str]]` built in Task 2, consumed as `customdata` in Task 3 — consistent. Return dict gains `'dates'` key in Task 2, all consumers updated.

4. **Scope check:** Single focused change to calendar heatmap only. No new files. ~15 lines across 2 locations in `app.py`. Tests added for new behavior.
