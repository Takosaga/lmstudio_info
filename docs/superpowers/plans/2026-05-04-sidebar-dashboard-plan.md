# Sidebar Dashboard Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the LMStudio dashboard from `page_fluid` to `page_sidebar` layout with sidebar controls and time-range-reactive KPI cards.

**Architecture:** Single-file Shiny app (`app.py`) refactored from `page_fluid` to `page_sidebar`. Sidebar contains three controls (Time Period, Model, Time Range). Main content has centered KPI cards and chart. All components react to time range selection.

**Tech Stack:** Python, Shiny 1.6+, Plotly, pandas, SQLite

---

### Task 1: Switch to `page_sidebar` layout and add sidebar controls

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Replace `ui.page_fluid` with `ui.page_sidebar` and add sidebar**

Replace the entire `app_ui` block. The new structure uses `ui.page_sidebar()` with `ui.sidebar()` containing three controls:

```python
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_select(
            "time_period",
            "Time Period",
            choices=["Daily", "Monthly"],
        ),
        ui.input_select(
            "model_filter",
            "Model",
            choices={"": "Top 5 Models"},
        ),
        ui.input_radio_buttons(
            "time_range",
            "Time Range",
            choices={
                "7": "7 days",
                "30": "30 days",
                "90": "90 days",
                "current_year": "Current Year",
                "all": "All Time",
            },
            selected="all",
            inline=True,
        ),
        open="desktop",
    ),
    # Main content goes here (KPI cards + chart)
    ui.include_css("assets/styles.css"),
    title="LMStudio Token Usage",
    fillable=True,
)
```

Also add `ui.include_css("assets/styles.css")` for custom centering styles.

- [ ] **Step 2: Run app to verify sidebar renders correctly**

Run: `uv run shiny run app.py`

Expected: Sidebar appears on the left with three controls. Main content area is empty (KPI cards not yet added).

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: switch to page_sidebar layout with sidebar controls"
```

---

### Task 2: Add centered KPI cards with time-range reactivity

**Files:**
- Modify: `app.py`
- Create: `app/assets/styles.css`

- [ ] **Step 1: Add centered KPI cards to main content area**

Replace the old KPI card row in `app_ui` (between sidebar and chart) with a centered row:

```python
    # KPI Cards - centered
    ui.row(
        ui.column(
            4,
            ui.card(
                ui.card_header("Total Tokens"),
                ui.output_text_verbatim("total_tokens"),
                class_="text-center",
            ),
        ),
        ui.column(
            4,
            ui.card(
                ui.card_header("Average Monthly Tokens"),
                ui.output_text_verbatim("avg_monthly"),
                class_="text-center",
            ),
        ),
        ui.column(
            4,
            ui.card(
                ui.card_header("Top Model"),
                ui.output_text_verbatim("top_model"),
                class_="text-center",
            ),
        ),
        class_="justify-content-center mb-4",
    ),
```

- [ ] **Step 2: Add CSS to center the KPI card row**

Create `app/assets/styles.css`:

```css
.kpi-row {
    display: flex;
    justify-content: center;
}
```

Apply the class to the row in `app_ui` by adding `class_="kpi-row"` to the `ui.row()` wrapper.

- [ ] **Step 3: Update KPI outputs to be reactive to time range**

In the `server` function, update the three output functions to filter by `input.time_range()`:

```python
@reactive.calc
def filtered_data():
    """Filter data based on selected time range."""
    if df is None:
        return None
    data = df.copy()
    data["_date"] = pd.to_datetime(data["created_at"])
    tr = input.time_range()
    if tr == "7":
        cutoff = data["_date"].max() - pd.Timedelta(days=7)
        data = data[data["_date"] >= cutoff]
    elif tr == "30":
        cutoff = data["_date"].max() - pd.Timedelta(days=30)
        data = data[data["_date"] >= cutoff]
    elif tr == "90":
        cutoff = data["_date"].max() - pd.Timedelta(days=90)
        data = data[data["_date"] >= cutoff]
    elif tr == "current_year":
        cutoff = pd.Timestamp.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        data = data[data["_date"] >= cutoff]
    # "all" returns unfiltered data
    return data
```

Update the three KPI outputs to use `filtered_data()` instead of the raw `df`:

```python
@output
@render.text
def total_tokens():
    data = filtered_data()
    if data is None or data.empty:
        return "No data available."
    total = int(data["token_count"].sum())
    return f"{total:,}"

@output
@render.text
def avg_monthly():
    data = filtered_data()
    if data is None or data.empty:
        return "No data available."
    data["_month"] = pd.to_datetime(data["created_at"]).dt.to_period("M")
    months = data["_month"].nunique()
    if months == 0:
        return "No data available."
    avg = int(data["token_count"].sum() / months)
    return f"{avg:,}"

@output
@render.text
def top_model():
    data = filtered_data()
    if data is None or data.empty:
        return "No data available."
    model_usage = data.groupby("model")["token_count"].sum().sort_values(ascending=False)
    if model_usage.empty:
        return "No data available."
    top = model_usage.index[0]
    tokens = int(model_usage.iloc[0])
    return f"{top}\n{tokens:,} tokens"
```

- [ ] **Step 4: Run app to verify KPI cards update with time range**

Run: `uv run shiny run app.py`

Expected: Selecting different time ranges updates all three KPI cards.

- [ ] **Step 5: Commit**

```bash
git add app.py app/assets/styles.css
git commit -m "feat: add centered KPI cards reactive to time range"
```

---

### Task 3: Update chart to use new model filter and time range

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Update chart title**

Change the chart header from `"Token Usage Over Time — Top 5 Models"` to `"Token Usage Over Time"`.

- [ ] **Step 2: Update `usage_chart` to handle time range filtering**

In the `usage_chart` server function, add time range filtering at the top (after `filtered_data()`):

```python
@output
@render_plotly()
def usage_chart():
    data = filtered_data()
    if data is None or data.empty:
        return None
    filtered = data.copy()
    # ... rest of existing chart logic ...
```

- [ ] **Step 3: Update model filter logic**

Replace the existing model filter logic in `usage_chart`:

```python
    # Model filter
    model = input.model_filter()
    if model == "Top 5 Models":
        # Get top 5 models by total token count
        top_5_models = (
            filtered.groupby("model")["token_count"]
            .sum()
            .nlargest(5)
            .index.tolist()
        )
        agg_top5 = filtered[filtered["model"].isin(top_5_models)].copy()
    elif model:
        agg_top5 = filtered[filtered["model"] == model].copy()
    else:
        agg_top5 = filtered.copy()
```

- [ ] **Step 4: Update legend title dynamically**

Change the legend title from `"Top 5 Models"` to show the correct label:

```python
    legend_title = "Top 5 Models" if model == "Top 5 Models" else "Model"
    fig.update_layout(legend_title=legend_title, ...)
```

- [ ] **Step 5: Run app to verify chart updates with model filter and time range**

Run: `uv run shiny run app.py`

Expected: Chart shows top 5 models by default. Changing model filter or time range updates chart correctly.

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: update chart for model filter and time range reactivity"
```

---

### Task 4: Final verification and cleanup

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Remove old `update_model_options` reactive effect**

The old `update_model_options` reactive effect that dynamically populates the model filter dropdown is no longer needed since the sidebar `input_select` with `open="desktop"` handles this differently. Remove it.

- [ ] **Step 2: Verify all three time range presets work correctly**

Test each preset: "7 days", "30 days", "90 days", "Current Year", "All Time".

- [ ] **Step 3: Verify KPI cards are centered**

Check that the KPI card row is centered on all screen sizes.

- [ ] **Step 4: Final commit**

```bash
git add app.py
git commit -m "chore: finalize sidebar layout and verify all features"
```

---
