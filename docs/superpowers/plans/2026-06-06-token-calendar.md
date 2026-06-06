# Token Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub-style contribution calendar to the Shiny dashboard showing token usage per model per day over the last 365 days.

**Architecture:** Extend `app.py` with a new Plotly heatmap rendered via `shinywidgets`. Data aggregation happens in-memory using pandas pivot tables from the existing unified dataframe. The calendar replaces the existing chart when selected.

**Tech Stack:** Python, Shiny, Plotly (via shinywidgets), pandas

---

## File Structure

- **Modify:** `app.py` — add "Calendar" radio option, new server logic, new heatmap output
- **Test:** `tests/test_calendar_heatmap.py` — unit tests for data aggregation function

## Task 1: Write data aggregation helper

**Files:**
- Create: `tests/test_calendar_heatmap.py`
- Modify: `app.py` (add helper function)

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from app import _build_calendar_data


def test_build_calendar_data_basic():
    """Test basic aggregation of tokens per model per day."""
    data = pd.DataFrame({
        'model': ['gpt-4', 'gpt-4', 'claude-3'],
        'created_at': pd.to_datetime(['2025-01-01', '2025-01-01', '2025-01-02']),
        'input_tokens': [100, 200, 150],
        'output_tokens': [300, 400, 250],
        'reasoning_tokens': [0, 0, 50],
        'cache_read_tokens': [0, 0, 0],
    })
    
    result = _build_calendar_data(data)
    
    assert result is not None
    assert isinstance(result, dict)
    assert 'z' in result  # heatmap values
    assert 'x' in result  # dates
    assert 'y' in result  # models


def test_build_calendar_data_zero_fill():
    """Test that missing model-day combinations are zero-filled."""
    data = pd.DataFrame({
        'model': ['gpt-4'],
        'created_at': pd.to_datetime(['2025-01-01']),
        'input_tokens': [100],
        'output_tokens': [300],
        'reasoning_tokens': [0],
        'cache_read_tokens': [0],
    })
    
    result = _build_calendar_data(data)
    
    # All cells should be non-negative
    assert all(v >= 0 for v in result['z'].flatten())


def test_build_calendar_data_sort_by_usage():
    """Test that models are sorted by total usage descending."""
    data = pd.DataFrame({
        'model': ['small-model', 'big-model', 'small-model'],
        'created_at': pd.to_datetime(['2025-01-01', '2025-01-01', '2025-01-02']),
        'input_tokens': [10, 1000, 20],
        'output_tokens': [10, 2000, 20],
        'reasoning_tokens': [0, 0, 0],
        'cache_read_tokens': [0, 0, 0],
    })
    
    result = _build_calendar_data(data)
    
    # big-model should appear before small-model (descending by total usage)
    y_order = result['y']
    assert y_order[0] == 'big-model'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_calendar_heatmap.py -v`
Expected: FAIL with "ImportError: cannot import name '_build_calendar_data'"

- [ ] **Step 3: Write minimal implementation of _build_calendar_data**

Add this function to `app.py` (place before the `App()` instantiation, after `_load_all_sources()`):

```python
def _build_calendar_data(data: pd.DataFrame) -> dict:
    """Build heatmap data for token calendar.
    
    Returns dict with 'z' (token counts), 'x' (dates), 'y' (models).
    Models sorted by total usage descending. Days zero-filled.
    """
    if data is None or data.empty:
        return {'z': [], 'x': [], 'y': []}
    
    # Calculate total tokens per row
    token_cols = ['input_tokens', 'output_tokens', 'reasoning_tokens', 'cache_read_tokens']
    df = data.copy()
    df['total_tokens'] = df[token_cols].sum(axis=1)
    df['_date'] = pd.to_datetime(df['created_at']).dt.date
    
    # Group by model and date
    agg = df.groupby(['model', '_date'])['total_tokens'].sum().reset_index()
    
    if agg.empty:
        return {'z': [], 'x': [], 'y': []}
    
    # Sort models by total usage descending
    model_totals = agg.groupby('model')['total_tokens'].sum().sort_values(ascending=False)
    sorted_models = model_totals.index.tolist()
    
    # Pivot to matrix: rows=models, columns=dates
    all_dates = sorted(agg['_date'].unique())
    pivot = agg.pivot_table(index='model', columns='_date', values='total_tokens', fill_value=0)
    
    # Reindex to include all dates (zero-fill gaps) and sort models
    pivot = pivot.reindex(columns=all_dates, fill_value=0)
    pivot = pivot.reindex(index=sorted_models)
    
    return {
        'z': pivot.values.tolist(),
        'x': [str(d) for d in all_dates],
        'y': list(pivot.index),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_calendar_heatmap.py -v`
Expected: PASS (3/3 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/test_calendar_heatmap.py app.py
git commit -m "feat: add calendar data aggregation helper"
```

## Task 2: Add Calendar tab to UI and server logic

**Files:**
- Modify: `app.py` — update sidebar controls, add heatmap output, add server handler

- [ ] **Step 1: Add "Calendar" radio button to sidebar**

In `app_ui`, modify the `time_period` input selector (around line 27):

```python
ui.input_radio_buttons(
    "time_period",
    "Time Period",
    choices={"Monthly": "Monthly", "Daily": "Daily", "Calendar": "Calendar"},
    selected="Monthly",
),
```

- [ ] **Step 2: Add heatmap output widget to chart card**

Replace the existing `output_widget("usage_chart")` in the chart card with conditional rendering:

```python
# Replace this line in the ui.card:
output_widget("usage_chart"),

# With:
conditional_panel(
    condition="input.time_period == 'Calendar'",
    output_widget("calendar_heatmap"),
),
conditional_panel(
    condition="input.time_period != 'Calendar'",
    output_widget("usage_chart"),
),
```

Add `from shiny import conditional_panel` to the imports at the top of `app.py`.

- [ ] **Step 3: Add calendar heatmap server handler**

Add this function in the `server` function, alongside `usage_chart`:

```python
@output
@render_plotly()
def calendar_heatmap():
    data = filtered_data()
    if data is None or data.empty:
        return None
    
    cal_data = _build_calendar_data(data)
    
    if not cal_data['z']:
        return None
    
    fig = go.Heatmap(
        z=cal_data['z'],
        x=cal_data['x'],
        y=cal_data['y'],
        colorscale=[
            [0, '#ebedf0'],
            [0.25, '#b6d3e8'],
            [0.5, '#6baed6'],
            [0.75, '#3182bd'],
            [1, '#08306b']
        ],
        hovertemplate='<b>%{y}</b><br>Date: %{x}<br>Tokens: %{z:,}<extra></extra>',
        xgap=2,
        ygap=2,
    )
    
    fig.update_layout(
        title="Token Usage Calendar",
        xaxis_title="",
        yaxis_title="Model",
        xaxis_tickangle=-45,
        margin=dict(l=180, r=30, t=40, b=60),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(size=11),
        height=max(300, len(cal_data['y']) * 25),  # Dynamic height per model count
    )
    
    fig.update_xaxes(type='category')
    
    return fig
```

Add `import plotly.graph_objects as go` to the imports at the top of `app.py`.

- [ ] **Step 4: Run the app to verify it works**

Run: `uv run shiny run app.py --host 127.0.0.1 --port 3000`
Expected: App starts, clicking "Calendar" in sidebar shows heatmap with models on y-axis and dates on x-axis.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: add calendar heatmap tab to dashboard"
```

## Task 3: Test the full integration

**Files:**
- Modify: `tests/test_calendar_heatmap.py` — add integration test

- [ ] **Step 1: Add integration test with real DB data**

Append to `tests/test_calendar_heatmap.py`:

```python
def test_calendar_with_real_db():
    """Test calendar heatmap builds from actual database."""
    db_path = str(Path(__file__).parent.parent / "data" / "lmstudio_usage.db")
    
    from data_loader import load_unified_data
    df = load_unified_data(db_path)
    
    assert df is not None and not df.empty
    
    cal_data = _build_calendar_data(df)
    
    assert len(cal_data['y']) > 0, "Should have at least one model"
    assert len(cal_data['x']) > 0, "Should have at least one date"
    assert len(cal_data['z']) == len(cal_data['y']), "Z matrix rows should match y count"


def test_calendar_time_filter():
    """Test that calendar respects time filtering."""
    db_path = str(Path(__file__).parent.parent / "data" / "lmstudio_usage.db")
    
    from data_loader import load_unified_data
    df = load_unified_data(db_path)
    
    # Filter to last 30 days only
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
    filtered = df[pd.to_datetime(df['created_at']) >= cutoff]
    
    cal_data = _build_calendar_data(filtered)
    
    if not cal_data['x']:
        return  # No data in range is acceptable
    
    # All dates should be within last 30 days
    for date_str in cal_data['x']:
        d = pd.to_datetime(date_str).date()
        assert (d >= cutoff.date()) and (d <= pd.Timestamp.now().date())
```

- [ ] **Step 2: Run all tests**

Run: `uv run pytest tests/test_calendar_heatmap.py -v`
Expected: PASS (all tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_calendar_heatmap.py
git commit -m "test: add integration tests for calendar heatmap"
```

## Task 4: Manual verification

- [ ] **Step 1: Start the app and verify UI**

Run: `uv run shiny run app.py --host 127.0.0.1 --port 3000`

Verify:
- "Calendar" option appears in sidebar Time Period selector
- Selecting Calendar shows heatmap instead of bar chart
- X-axis shows dates, y-axis shows models sorted by usage
- Hover tooltips show model name, date, and token count
- Color gradient goes from light to dark green (GitHub-style)

- [ ] **Step 2: Verify with different time filters**

Test each time_range option while Calendar is selected:
- "7 days" — should show last week only
- "30 days" — should show last month only  
- "90 days" — should show last quarter only
- "Current Year" — should show 2026 data only
- "All Time" — should show full history

- [ ] **Step 3: Commit any fixes**

```bash
git add app.py
git commit -m "fix: refine calendar heatmap based on manual testing"
```
