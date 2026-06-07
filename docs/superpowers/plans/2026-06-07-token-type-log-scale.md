# Token Type Chart Log Scale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply logarithmic y-axis scale to the token-type breakdown chart so output tokens (~1% of input) are clearly visible alongside input tokens.

**Architecture:** A single-line change in the `usage_chart` server function's token-type branch: add `yaxis=dict(type='log')` to the Plotly figure layout and update the y-axis label to indicate log scale. The model-based chart remains unchanged.

**Tech Stack:** Python 3.12, Shiny, Plotly Express, pandas

---

### Task 1: Add log-scale behavior to token-type chart

**Files:**
- Modify: `app.py:~405-420` (the `usage_chart` server function, token-type branch)

- [ ] **Step 1: Write a test that verifies log scale is applied for token_type breakdown**

```python
# tests/test_log_scale.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shiny import run_cmd  # not needed, we test the fig directly


def test_token_type_chart_has_log_yaxis():
    """When breakdown_by is token_type, the usage chart y-axis should be log scale."""
    # We can't easily mock Shiny inputs in unit tests, so we extract the
    # figure-building logic and test it directly. Since the change is a single
    # fig.update_layout() call inside the server function, we verify by
    # reading the source code for the expected call pattern.
    app_py = Path(__file__).parent.parent / "app.py"
    source = app_py.read_text()

    # After the token-type branch's px.bar() call, there should be a
    # fig.update_layout() that includes yaxis=dict(type='log')
    assert "yaxis=dict(type='log')" in source, \
        "Token type chart should use log scale on y-axis"


def test_token_type_yaxis_label_indicates_log_scale():
    """The y-axis label for token-type chart should mention 'log'."""
    app_py = Path(__file__).parent.parent / "app.py"
    source = app_py.read_text()

    # In the token-type branch, the labels dict should have
    # 'token_count': 'Total Tokens (log scale)' or similar
    assert "Total Tokens (log scale)" in source or \
           "'token_count'" in source and "log" in source.split("token_type")[1].split("fig.update_layout")[0], \
        "Token type y-axis label should indicate log scale"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_log_scale.py -v`
Expected: FAIL — source does not yet contain `yaxis=dict(type='log')`

- [ ] **Step 3: Apply the minimal code changes in app.py**

In the `usage_chart` server function, within the token-type branch (the `if input.breakdown_by() == "token_type":` block), make two changes:

**Change A — Update the y-axis label in the `px.bar()` call's `labels` dict.**

Find the existing `labels=` argument in the `px.bar()` call inside the token-type branch and change:
```python
labels={'_time': 'Time', 'token_count': 'Tokens', 'token_type': 'Token Type'},
```
to:
```python
labels={'_time': 'Time', 'token_count': 'Total Tokens (log scale)', 'token_type': 'Token Type'},
```

**Change B — Add log scale to the `fig.update_layout()` call inside the token-type branch.**

Find the `fig.update_layout()` call that follows `fig = px.bar(...)` in the token-type branch. It currently has:
```python
fig.update_traces(
    hovertemplate="<b>%{customdata[0]}</b><br>Tokens: %{customdata[1]:,}<br>Period share: %{customdata[2]}<extra></extra>",
    textposition="inside",
)
```

Add a `fig.update_layout()` call right after it (or add `yaxis=dict(type='log')` to the existing layout update if one exists in this branch). The exact code to insert after the `fig.update_traces(...)` block:

```python
            fig.update_layout(
                yaxis=dict(type='log'),
            )
```

**Note:** Do NOT modify the model-based branch (the `else:` block) at all. It must remain unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_log_scale.py -v`
Expected: PASS — source now contains `yaxis=dict(type='log')` and the updated label.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest`
Expected: All existing tests pass (no regression).

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_log_scale.py
git commit -m "feat: use log scale for token type breakdown chart"
```

---

### Task 2: Manual verification

- [ ] **Step 1: Run the app and verify visually**

Run: `uv run shiny run app.py`

Then in browser, navigate to `http://127.0.0.1:3000`, select:
- Breakdown by: **Token Type**
- Time Period: Monthly (or Current Year)

Verify:
1. Output token bars are clearly visible (not 1px slivers)
2. Y-axis label reads "Total Tokens (log scale)" or similar
3. Hover tooltips still show raw token counts (not log-transformed values)
4. Input and output bars stack correctly

- [ ] **Step 2: Verify model-based chart is unchanged**

Switch Breakdown by to **Model**. Verify the chart uses a linear y-axis as before (bars proportional to absolute token counts).

- [ ] **Step 3: Commit any fixups if needed**

```bash
git add app.py
git commit -m "fix: adjust log scale presentation after manual review"
```
