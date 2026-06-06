# Remove Source Filter & Token Type Filter to Input/Output Only

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the Source filter from the dashboard UI and restrict the token-type breakdown chart to only show Input Tokens and Output Tokens, while keeping all KPI totals and calendar heatmap unchanged.

**Architecture:** Two surgical edits in `app.py` — delete the source filter radio button from the sidebar, remove its filtering logic in `filtered_data()`, and narrow the token-type column list + name mapping in `usage_chart()`. No new files, no database changes, no test file changes needed.

**Tech Stack:** Python 3.12, Shiny (web framework), Plotly (charts), pandas (data processing)

---

### Task 1: Remove Source Selector from UI Sidebar

**Files:**
- Modify: `app.py:245-250`

- [ ] **Step 1: Delete the source_filter radio button block**

In `app.py`, find lines 245–250 and delete this entire block:

```python
        ui.input_radio_buttons(
            "source_filter",
            "Source",
            choices={"lmstudio": "LMStudio", "opencode": "OpenCode", "pi": "Pi", "all": "All Sources"},
            selected="lmstudio",
            inline=True,
        ),
```

After deletion, the sidebar should have exactly 4 `ui.input_radio_buttons` calls: `time_period`, `breakdown_by`, `time_range`. There should be no trailing comma after the last one (`time_range`) — remove it. The closing paren for `ui.sidebar(` should directly follow `time_range`'s closing paren.

- [ ] **Step 2: Verify syntax**

Run:
```bash
cd /home/takosaga/Projects/lmstudio_info && uv run python -c "import ast; ast.parse(open('app.py').read()); print('Syntax OK')"
```
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
cd /home/takosaga/Projects/lmstudio_info && git add app.py && git commit -m "ui: remove source filter selector from sidebar"
```

### Task 2: Remove Source Filtering Logic in Server

**Files:**
- Modify: `app.py` (server function `filtered_data`)

- [ ] **Step 1: Delete the source filter block in `filtered_data()`**

Find this block inside the `filtered_data()` server function and delete it entirely:

```python
        # Source filter
        src = input.source_filter()
        if src and src != "all":
            data = data[data["source"] == src]
```

After deletion, the next line after the NaN fill loop should be `if data.empty:`.

- [ ] **Step 2: Update filtered_data docstring**

Change the docstring from:
```python
    def filtered_data(self):
        """Filter data based on selected time range and source."""
```
to:
```python
    def filtered_data(self):
        """Filter data based on selected time range (all sources)."""
```

- [ ] **Step 3: Verify no dangling references**

Run:
```bash
cd /home/takosaga/Projects/lmstudio_info && grep -n "source_filter" app.py
```
Expected: zero results (no remaining references to `source_filter`)

- [ ] **Step 4: Run existing tests**

```bash
cd /home/takosaga/Projects/lmstudio_info && uv run pytest -v
```
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
cd /home/takosaga/Projects/lmstudio_info && git add app.py && git commit -m "server: remove source filtering logic from filtered_data"
```

### Task 3: Filter Token Type Chart to Input + Output Only

**Files:**
- Modify: `app.py` (inside `usage_chart()` output function, `token_type` branch)

- [ ] **Step 1: Narrow token_cols list**

Find the line inside the `if input.breakdown_by() == "token_type":` block that reads:

```python
            token_cols = ['input_tokens', 'output_tokens', 'reasoning_tokens', 'cache_read_tokens']
```

Change it to:

```python
            token_cols = ['input_tokens', 'output_tokens']
```

This is the ONLY occurrence of `token_cols` in the `token_type` branch. Do NOT change the `_build_calendar_data()` function which also uses a `token_cols` variable — that one stays as-is with all four types.

- [ ] **Step 2: Update token type name mapping**

Find this mapping and replace it:

```python
            # Format token type names for display
            agg_melted['token_type'] = agg_melted['token_type'].map({
                'input_tokens': 'Input',
                'output_tokens': 'Output',
                'reasoning_tokens': 'Reasoning',
                'cache_read_tokens': 'Cache Read',
            })
```

Replace with:

```python
            # Format token type names for display
            agg_melted['token_type'] = agg_melted['token_type'].map({
                'input_tokens': 'Input Tokens',
                'output_tokens': 'Output Tokens',
            })
```

- [ ] **Step 3: Update displayed_types and type_order**

The existing code computes `displayed_types` dynamically from the data. After narrowing `token_cols`, this will naturally only produce `['Input Tokens', 'Output Tokens']`. No code change needed here — the logic at lines ~490–496 already handles dynamic type discovery:

```python
            # Determine displayed token types (those with non-zero counts)
            displayed_types = agg_melted['token_type'].unique().tolist()
            if not displayed_types:
                return None

            # Order consistently
            type_order = ['Input', 'Output', 'Reasoning', 'Cache Read']
            type_order = [t for t in type_order if t in displayed_types]
```

Change the hardcoded `type_order` list to match the new names:

```python
            type_order = ['Input Tokens', 'Output Tokens']
```

- [ ] **Step 4: Update palette**

Find the palette definition and replace it:

```python
            palette = ['#457b9d', '#e63946', '#2a9d8f', '#f4a261']
```

Change to:

```python
            palette = ['#457b9d', '#e63946']
```

- [ ] **Step 5: Verify no dangling references**

Run:
```bash
cd /home/takosaga/Projects/lmstudio_info && grep -n "Reasoning\|Cache Read" app.py | grep -v "_build_calendar_data"
```
Expected: zero results (no remaining references to old token type names outside the calendar function)

- [ ] **Step 6: Verify syntax**

Run:
```bash
cd /home/takosaga/Projects/lmstudio_info && uv run python -c "import ast; ast.parse(open('app.py').read()); print('Syntax OK')"
```
Expected: `Syntax OK`

- [ ] **Step 7: Run existing tests**

```bash
cd /home/takosaga/Projects/lmstudio_info && uv run pytest -v
```
Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
cd /home/takosaga/Projects/lmstudio_info && git add app.py && git commit -m "chart: restrict token type breakdown to input and output only"
```

### Task 4: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Confirm calendar heatmap is untouched**

Run:
```bash
cd /home/takosaga/Projects/lmstudio_info && grep -A2 "token_cols = " app.py
```
Expected output shows TWO occurrences of `token_cols`:
1. Inside `_build_calendar_data()` — still has all 4 types: `['input_tokens', 'output_tokens', 'reasoning_tokens', 'cache_read_tokens']`
2. Inside `usage_chart()` token_type branch — now has 2 types: `['input_tokens', 'output_tokens']`

- [ ] **Step 2: Confirm KPI functions are untouched**

Run:
```bash
cd /home/takosaga/Projects/lmstudio_info && grep -n "token_count" app.py | head -10
```
Expected: `total_tokens`, `avg_value`, and `top_model` outputs still reference `token_count` (all types summed)

- [ ] **Step 3: Confirm no stale source_filter references**

Run:
```bash
cd /home/takosaga/Projects/lmstudio_info && grep -rn "source_filter" app.py
```
Expected: zero results

- [ ] **Step 4: Run full test suite**

```bash
cd /home/takosaga/Projects/lmstudio_info && uv run pytest -v
```
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
cd /home/takosaga/Projects/lmstudio_info && git add app.py && git commit -m "verify: confirm calendar and KPIs unchanged, no stale references"
```
