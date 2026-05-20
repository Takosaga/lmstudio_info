# Model Filter Dropdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a multi-select dropdown to filter charts by individual models, defaulting to showing all top 5 models.

**Architecture:** Add Shiny's built-in `input_select(multiple=True)` widget to the sidebar in `app.py`. The dropdown uses selectize.js natively — searchable, tag-style selection. Default is all models selected (preserving current top-5 behavior). A reactive filter in `filtered_data()` applies the model selection, and `usage_chart()` uses the user's selection instead of hardcoded top-5 when explicitly narrowed.

**Tech Stack:** Python 3.12, Shiny, Plotly, pandas, SQLite

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `app.py` | Modify | Add model filter dropdown to sidebar; add model filter to `filtered_data()`; update `usage_chart()` to respect user selection |

No new files or tests needed — this is a pure UI/UX change in the Shiny app.

---

### Task 1: Add model_filter input_select to sidebar

**Files:**
- Modify: `app.py:68-75` (sidebar section)

- [ ] **Step 1: Add the multi-select dropdown after existing radio buttons**

Insert this block inside the `ui.sidebar(...)` call, after the `time_range` radio buttons and before `open="desktop"` (after line ~85):

```python
# Capture all models from loaded data for dropdown options
_all_models = list(df["model"].dropna().unique()) if df is not None else []
ui.input_select(
    "model_filter",
    "Models",
    choices={m: m for m in sorted(_all_models)},
    selected=_all_models if _all_models else None,
    multiple=True,
),
```

This adds a searchable multi-select dropdown. When `df` is loaded at module level (line 50), `_all_models` captures every unique model name. Default `selected` includes all models — current behavior preserved.

- [ ] **Step 2: Run app to verify**

Run: `uv run shiny run app.py &`
Expected: App starts on `127.0.0.1:3000`, sidebar shows new "Models" dropdown with all model names listed and pre-selected.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add model filter multi-select dropdown to sidebar"
```

---

### Task 2: Add model filter logic to filtered_data()

**Files:**
- Modify: `app.py:128-157` (filtered_data reactive calc)

- [ ] **Step 1: Add model filtering after source filter**

In the `filtered_data()` function, after the source filter block (after line ~137, before `if data.empty:`), add:

```python
# Model filter
models = input.model_filter()
if models:
    data = data[data["model"].isin(models)]
```

Full context — the modified section of `filtered_data()` should look like this:

```python
@reactive.calc
def filtered_data():
    """Filter data based on selected time range and source."""
    if df is None:
        return None
    data = df.copy()

    # Source filter
    src = input.source_filter()
    if src and src != "all":
        data = data[data["source"] == src]

    # Model filter — only apply when user has made a selection
    models = input.model_filter()
    if models:
        data = data[data["model"].isin(models)]

    if data.empty:
        return data
    ...
```

When `models` is empty (all selected, default), the filter is skipped and all data passes through unchanged.

- [ ] **Step 2: Run app to verify**

Run: `uv run shiny run app.py &`
Expected: Selecting/deselecting models in the dropdown immediately filters the chart. Default behavior (all selected) still shows top 5 models.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add model filter to filtered_data reactive calc"
```

---

### Task 3: Update usage_chart() to respect user model selection

**Files:**
- Modify: `app.py:216-378` (usage_chart output)

- [ ] **Step 1: Replace hardcoded top-5 with user selection for model-based charts**

In `usage_chart()`, the current logic (lines ~220-230) always filters to top 5 models when `breakdown_by != "token_type"`. Replace this block:

```python
# Always show top 5 models (unless breaking down by token type)
if input.breakdown_by() != "token_type":
    top_5_models = (
        agg_top5.groupby("model")["token_count"]
        .sum()
        .nlargest(5)
        .index.tolist()
    )
    agg_top5 = agg_top5[agg_top5["model"].isin(top_5_models)].copy()
```

With:

```python
# Use user's model selection if explicitly narrowed; otherwise show top 5
if input.breakdown_by() != "token_type":
    models = input.model_filter()
    total_models = len(df["model"].dropna().unique()) if df is not None else 0
    if models and len(models) < total_models:
        # User has narrowed selection — use their models
        agg_top5 = agg_top5[agg_top5["model"].isin(models)].copy()
    else:
        # Default: show top 5 by token count
        top_5_models = (
            agg_top5.groupby("model")["token_count"]
            .sum()
            .nlargest(5)
            .index.tolist()
        )
        agg_top5 = agg_top5[agg_top5["model"].isin(top_5_models)].copy()
```

This checks if the user has made an explicit narrowing selection. If so, use their models. Otherwise, fall back to the existing top-5 behavior.

- [ ] **Step 2: Update displayed_models calculation to use filtered data**

The `displayed_models` variable at line ~314 already reads from `agg_top5.groupby("model")["token_count"].sum().nlargest(5).index`, which will now correctly reflect the user's selection. No change needed here — it adapts automatically because `agg_top5` is already filtered by the logic in Step 1.

- [ ] **Step 3: Run app to verify**

Run: `uv run shiny run app.py &`
Expected:
- Default (all selected): chart shows top 5 models, legend says "Top 5 Models"
- User selects 2 models: chart shows only those 2, legend updates accordingly
- User selects 1 model: chart shows single series
- User deselects all: chart shows "No data available" or empty state

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: use user model selection instead of hardcoded top-5 in chart"
```

---

### Task 4: Run existing tests to confirm no regressions

**Files:**
- Test: `tests/test_loader.py`, `tests/test_extraction.py`, `tests/test_database.py` (if any exist)

- [ ] **Step 1: Run all tests**

Run: `uv run pytest`
Expected: All existing tests pass. No new tests needed for this change.

- [ ] **Step 2: Commit any fixes if tests fail**

If tests fail, fix the issues and amend the last commit:

```bash
git add -A
git commit --amend --no-edit
```
