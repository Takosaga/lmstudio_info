# Tool Calls KPI Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Total Tool Calls" KPI card to the Shiny dashboard showing summed `tool_call_count` for the selected time period and source filters.

**Architecture:** Two reactive outputs mirroring the existing KPI pattern, plus a 4th card in the KPI row. Column widths shift from 4-4-4 to 3-3-3-3 for even distribution.

**Tech Stack:** Python, Shiny, Plotly, pandas, SQLite (schema unchanged)

---

### Task 1: Add tool calls KPI outputs and update KPI row layout

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Update the KPI row to 4 columns**

In `app.py`, replace the existing 3-column KPI row with a 4-column layout. Change every `ui.column(4, ...)` to `ui.column(3, ...)` and add a 4th card for tool calls:

```python
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
```

The KPI row currently spans lines 89–115. Replace the entire `ui.row(...)` block with the above.

- [ ] **Step 2: Add reactive outputs for total_tool_calls**

In the `server` function (after the existing `top_model` output around line 214), add two new outputs following the exact same pattern as the other KPI cards:

```python
    @output
    @render.text
    def total_tool_calls_header():
        return "Total Tool Calls"

    @output
    @render.text
    def total_tool_calls():
        data = filtered_data()
        if data is None or data.empty:
            return "No data available."
        total = int(data["tool_call_count"].sum())
        return f"{total:,}"
```

These go inside the `server` function, after the `top_model` output and before the `usage_chart` output.

- [ ] **Step 3: Run the app to verify visually**

```bash
uv run shiny run app.py
```

Open http://127.0.0.1:3000 in a browser. Verify:
- 4 KPI cards display evenly across the row
- "Total Tool Calls" card shows a comma-formatted number (e.g., `1,234`)
- Card updates when changing time range or source filters
- Card shows "No data available." when no conversations exist

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add Total Tool Calls KPI card to dashboard"
```
