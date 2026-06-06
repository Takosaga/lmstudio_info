# Dashboard Calendar Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the calendar heatmap from being controlled by the sidebar's Time Period selector to a fixed, always-visible position at the top of the dashboard, independent of the bar chart below.

**Architecture:** Extract the existing inline calendar figure-building code from `usage_chart()` into a standalone `_build_calendar_figure(cal_data)` helper. Add a new reactive calc `_calendar_data()` that always returns 52 weeks from last data entry (source-filtered only). Reorder the UI: calendar → KPI cards → bar chart. Remove "Calendar" from the Time Period selector.

**Tech Stack:** Python, Shiny (dashboard framework), Plotly (charts), pandas (data)

---

## Task 1: Extract `_build_calendar_figure()` helper

**Files:**
- Modify: `app.py` — extract calendar figure builder from inline code into reusable function

This task extracts the ~80 lines of Plotly figure-building logic currently inside `usage_chart()` under `if input.time_period() == "Calendar"` into a standalone function `_build_calendar_figure(cal_data)` that returns a `go.Figure`. This avoids duplication since the new top-level calendar output will use the same code.

- [ ] **Step 1: Read the current inline calendar code in `usage_chart()`**

Read `app.py` lines 275–360 to locate the exact block under `if input.time_period() == "Calendar":`. This is the code that builds shapes, hover text, and the Plotly figure for the heatmap. You need this as context — do NOT edit yet.

- [ ] **Step 2: Write `_build_calendar_figure()` helper**

Insert the following function in `app.py` right after the existing `_build_calendar_data()` function (after line ~114, before the `# --- UI ---` comment):

```python
def _build_calendar_figure(cal_data: dict) -> go.Figure | None:
    """Build a Plotly Figure for the GitHub-style calendar heatmap.

    Takes the output of `_build_calendar_data()` and returns a fully-configured
    go.Figure with green-shaded cells, month labels on top, day labels on left,
    and hover text showing date + token count. Returns None if cal_data is empty.
    """
    if not cal_data.get('z'):
        return None

    n_cols = len(cal_data['z'][0])
    cell_size = 28  # pixel size of each square
    gap = 2         # white gap between cells
    step = cell_size + gap  # pitch per cell
    margin_l, margin_r, margin_t, margin_b = 100, 40, 50, 70
    width = n_cols * step + margin_l + margin_r - gap
    height = 7 * step + margin_t + margin_b - gap

    # Build shapes: one rectangle per cell (crisp discrete squares, no anti-aliasing)
    shapes = []
    for row in range(7):
        for col in range(n_cols):
            tokens = cal_data['z'][row][col]
            if tokens > 0:
                # Map token count to green shade
                pct = min(tokens / 100_000, 1.0)
                if pct < 0.05:
                    color = '#b6e2b4'
                elif pct < 0.15:
                    color = '#9be9a8'
                elif pct < 0.30:
                    color = '#40c463'
                elif pct < 0.50:
                    color = '#30a14e'
                elif pct < 0.75:
                    color = '#2ea44f'
                else:
                    color = '#216e39'
            else:
                color = '#ebedf0'  # no activity = gray

            date_str = cal_data['date_strings'][row][col]
            shapes.append(go.layout.Shape(
                type="rect",
                xref="x", yref="y",
                x0=col * step, x1=(col + 1) * step - gap,
                y0=row * step, y1=(row + 1) * step - gap,
                fillcolor=color,
                line=dict(width=0),
            ))

    # Hover text via customdata on a transparent scatter trace
    hover_x = []
    hover_y = []
    hover_text = []
    for row in range(7):
        for col in range(n_cols):
            tokens = cal_data['z'][row][col]
            date_str = cal_data['date_strings'][row][col]
            if date_str:
                hover_x.append(col * step + cell_size / 2)
                hover_y.append(row * step + cell_size / 2)
                hover_text.append(f'<b>{date_str}</b><br>Tokens: {tokens:,}')

    fig = go.Figure(data=[
        go.Scatter(
            x=hover_x, y=hover_y,
            mode='markers',
            marker=dict(size=1, opacity=0),  # invisible markers for hover
            text=hover_text,
            hovertemplate='%{text}<extra></extra>',
            showlegend=False,
        ),
    ])
    fig.update_layout(shapes=shapes)
    fig.update_layout(
        xaxis_title="",
        yaxis_title="",
        margin=dict(l=margin_l, r=margin_r, t=margin_t, b=margin_b),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(size=11),
        width=width,
        height=height,
    )

    fig.update_xaxes(
        type='linear',
        range=[-gap, n_cols * step],
        tickvals=[col * step + cell_size / 2 for col in cal_data.get('tickvals', [])],
        ticktext=cal_data.get('ticktext', []),
        tickangle=-15,
        side='top',
        showgrid=False,
    )
    fig.update_yaxes(
        range=[-gap, 7 * step],
        dtick=step,
        tickvals=[row * step + cell_size / 2 for row in range(7)],
        ticktext=['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
        tickangle=0,
        showgrid=False,
    )
    return fig
```

- [ ] **Step 3: Verify the file still parses**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('OK')"`
Expected: `OK` (no syntax errors)

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "refactor: extract _build_calendar_figure helper from usage_chart"
```

---

## Task 2: Add `_calendar_data()` reactive calc and `calendar_chart` output

**Files:**
- Modify: `app.py` — new reactive calc, new output

This task adds the new reactive calculation that always returns 52-week calendar data (source-filtered only), and a new Plotly output that renders it at the top.

- [ ] **Step 1: Add `_calendar_data()` reactive calc**

Insert this new reactive calc inside the `server()` function, right after the existing `filtered_data()` calc (after the `return data` line of `filtered_data`, before `total_tokens_header`):

```python
    @reactive.calc
    def calendar_data():
        """Calendar heatmap data — always 52 weeks from last entry, source-filtered only."""
        if df is None:
            return None
        data = df.copy()

        # Source filter only (no time range filter for calendar)
        src = input.source_filter()
        if src and src != "all":
            data = data[data["source"] == src]

        if data.empty:
            return None

        return _build_calendar_data(data)
```

- [ ] **Step 2: Add `calendar_chart` output**

Insert this new output right after the `total_tool_calls` output (before the `usage_chart` output):

```python
    @output
    @render_plotly()
    def calendar_chart():
        data = calendar_data()
        if data is None:
            return None
        return _build_calendar_figure(data)
```

- [ ] **Step 3: Update `usage_chart()` to remove the Calendar branch**

In the `usage_chart()` function, find and remove the entire block from `# === CALENDAR HEATMAP MODE ===` through to (but NOT including) `agg_top5 = data.copy()`. The code should go directly from the empty-data check to `agg_top5 = data.copy()`.

Specifically, delete everything between:
```python
        # === CALENDAR HEATMAP MODE ===
        if input.time_period() == "Calendar":
            ...
            return fig
```
and the line:
```python
        agg_top5 = data.copy()
```

After removal, `usage_chart()` should look like:
```python
    @output
    @render_plotly()
    def usage_chart():
        data = filtered_data()
        if data is None or data.empty:
            return None

        agg_top5 = data.copy()
        # ... rest of the function unchanged
```

- [ ] **Step 4: Verify the file still parses**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('OK')"`
Expected: `OK` (no syntax errors)

- [ ] **Step 5: Run existing tests to ensure no regressions**

Run: `uv run pytest tests/test_calendar_heatmap.py -v`
Expected: All existing calendar tests pass (they test `_build_calendar_data` which is unchanged).

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: add _calendar_data reactive calc and calendar_chart output"
```

---

## Task 3: Reorder UI — calendar at top, KPI cards below, bar chart at bottom

**Files:**
- Modify: `app.py` — rearrange `app_ui` elements

This task reorders the layout in `app_ui`: sidebar → calendar chart → KPI row → bar chart card.

- [ ] **Step 1: Update `app_ui` to reorder elements**

Replace the entire `app_ui` definition (from `app_ui = ui.page_sidebar(` through `fillable=True,`) with:

```python
# --- UI ---
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_radio_buttons(
            "time_period",
            "Time Period",
            choices={"Monthly": "Monthly", "Daily": "Daily"},
            selected="Monthly",
        ),
        ui.input_radio_buttons(
            "source_filter",
            "Source",
            choices={"lmstudio": "LMStudio", "opencode": "OpenCode", "all": "Both"},
            selected="lmstudio",
            inline=True,
        ),
        ui.input_radio_buttons(
            "breakdown_by",
            "Breakdown by",
            choices={"model": "Model", "token_type": "Token Type"},
            selected="model",
            inline=True,
        ),
        ui.input_radio_buttons(
            "time_range",
            "Time Range",
            choices={
                "90": "90 days",
                "current_year": "Current Year",
                "all": "All Time",
            },
            selected="current_year",
            inline=True,
        ),
        open="desktop",
    ),
    # Calendar Heatmap — always visible at top
    ui.card(
        ui.card_header("Token Usage Calendar"),
        output_widget("calendar_chart"),
    ),
    # KPI Cards - centered
    ui.row(
        ui.column(
            3,
            ui.card(
                ui.output_text_verbatim("total_tokens_header"),
                ui.output_text_verbatim("total_tokens"),
                class_="text-center",
            ),
        ),
        ui.column(
            3,
            ui.card(
                ui.output_text_verbatim("avg_header"),
                ui.output_text_verbatim("avg_value"),
                class_="text-center",
            ),
        ),
        ui.column(
            3,
            ui.card(
                ui.output_text_verbatim("top_model_header"),
                ui.output_text_verbatim("top_model"),
                class_="text-center",
            ),
        ),
        ui.column(
            3,
            ui.card(
                ui.output_text_verbatim("total_tool_calls_header"),
                ui.output_text_verbatim("total_tool_calls"),
                class_="text-center",
            ),
        ),
        class_="justify-content-center mb-4 kpi-row",
    ),
    # Bar Chart — Monthly or Daily
    ui.card(
        ui.card_header("Token Usage Over Time"),
        output_widget("usage_chart"),
    ),
    ui.include_css(str(Path(__file__).parent / "assets" / "styles.css")),
    fillable=True,
)
```

Key changes in this block:
- `"time_period"` choices changed from `{"Monthly": "Monthly", "Daily": "Daily", "Calendar": "Calendar"}` to `{"Monthly": "Monthly", "Daily": "Daily"}`
- `"time_period"` selected changed from `"Calendar"` to `"Monthly"` (since Calendar is gone)
- Added calendar card UI right after sidebar, before KPI row
- Bar chart card stays at bottom with same header

- [ ] **Step 2: Verify the file still parses**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('OK')"`
Expected: `OK` (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: reorder UI — calendar at top, KPI cards below, bar chart at bottom"
```

---

## Task 4: Update `top_model` output to one-line format

**Files:**
- Modify: `app.py` — change return format of `top_model()` output

This task changes the "Top Model" KPI card from a two-line display to a single line.

- [ ] **Step 1: Find and update the `top_model` output function**

In the server function, find the existing `top_model` output (around line ~235):

```python
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

Replace the last line (the `return` statement) to produce one-line output:

```python
        return f"{top} — {tokens:,} tokens"
```

The full function becomes:

```python
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
        return f"{top} — {tokens:,} tokens"
```

- [ ] **Step 2: Verify the file still parses**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('OK')"`
Expected: `OK` (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "style: format top_model KPI card as one-line display"
```

---

## Task 5: Clean up `update_time_range_choices()` effect

**Files:**
- Modify: `app.py` — remove Calendar-specific logic from filter updater

The `update_time_range_choices()` reactive effect currently has a branch for `"Calendar"` that does nothing. Since Calendar is removed from the selector, this branch should be cleaned up.

- [ ] **Step 1: Update `update_time_range_choices()`**

Find and replace the entire `update_time_range_choices` function:

```python
    # Dynamic filter visibility based on time_period selection
    @reactive.effect
    def update_time_range_choices():
        period = input.time_period()

        if period == "Daily":
            ui.update_radio_buttons(
                "breakdown_by",
                choices={"model": "Model", "token_type": "Token Type"},
                selected="model",
            )
            ui.update_radio_buttons(
                "time_range",
                choices={"7": "7 days", "30": "30 days", "90": "90 days"},
                selected="30",
            )
        else:  # Monthly
            ui.update_radio_buttons(
                "breakdown_by",
                choices={"model": "Model", "token_type": "Token Type"},
                selected="model",
            )
            ui.update_radio_buttons(
                "time_range",
                choices={
                    "90": "90 days",
                    "current_year": "Current Year",
                    "all": "All Time",
                },
                selected="current_year",
            )
```

The `if period == "Calendar":` branch is removed. Now it's just `if period == "Daily":` / `else: (Monthly)`.

- [ ] **Step 2: Verify the file still parses**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('OK')"`
Expected: `OK` (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "cleanup: remove Calendar branch from update_time_range_choices"
```

---

## Task 6: Final verification — run all tests

**Files:**
- Run: `uv run pytest` (all tests)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v`
Expected: All tests pass. The existing calendar heatmap tests (`test_calendar_heatmap.py`) should still pass since `_build_calendar_data()` is unchanged. The new `_build_calendar_figure()` helper is not separately tested (it's an internal rendering function; the existing `test_calendar_with_real_db` and `test_usage_chart_calendar_hover` test it indirectly through the old inline code path, which now passes via the new output).

- [ ] **Step 2: Quick smoke test — start the app**

Run: `uv run python -c "from app import app; print('App loads OK')"`
Expected: `App loads OK` (no import errors, no database issues)

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "test: verify all tests pass after calendar separation refactor"
```

---

## Spec Coverage Check

| Spec Requirement | Task | Status |
|---|---|---|
| Extract `_build_calendar_figure()` helper | Task 1 | ✓ |
| Add `_calendar_data()` reactive calc | Task 2, Step 1 | ✓ |
| Add `calendar_chart` output | Task 2, Step 2 | ✓ |
| Remove Calendar branch from `usage_chart()` | Task 2, Step 3 | ✓ |
| Update KPI card `top_model` to one-line format | Task 4 | ✓ |
| Remove "Calendar" from `time_period` choices | Task 3, Step 1 | ✓ |
| Reorder UI: calendar → KPI → bar chart | Task 3, Step 1 | ✓ |
| Clean up Calendar branch in `update_time_range_choices()` | Task 5 | ✓ |
| No changes to other files | — (all tasks only touch `app.py`) | ✓ |

## Placeholder Scan

No TBD, TODO, or vague requirements found. All code blocks are complete and self-contained.
