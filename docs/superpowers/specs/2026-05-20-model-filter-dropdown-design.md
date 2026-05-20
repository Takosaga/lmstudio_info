# Model Filter Dropdown Design

**Date:** 2026-05-20
**Feature:** Add a multi-select dropdown to filter charts by individual models, defaulting to showing all top 5 models.

## UI Changes

- Add `ui.input_select("model_filter", "Models", ..., multiple=True, selected=None)` to the sidebar in `app.py`, after the existing radio button filters (after line ~68)
- `selected=None` means all available models are pre-selected by default — preserves current behavior
- Uses Shiny's built-in selectize.js widget: searchable dropdown with tag-style selection

## Server Logic Changes

### New reactive filter in `filtered_data()`
- Read `input.model_filter()` and apply an additional filter to exclude rows where the model is not in the user's selection
- When `model_filter` is empty or includes all models (default), skip this filter entirely — data passes through unchanged

### Updated chart logic in `usage_chart()`
- When `breakdown_by == "model"`: if the user has explicitly narrowed their model selection, use that selection as the set of displayed models instead of the hardcoded top-5 calculation
- If no explicit narrowing (all selected), fall back to current top-5 behavior
- When `breakdown_by == "token_type"`, model filter has no effect (chart shows token types, not models)

## Data Flow

1. Sidebar: user selects/deselects models via multi-select dropdown
2. Selection triggers reactive update → `filtered_data()` re-runs with model filter applied
3. `usage_chart()` reads the filtered data and renders only selected models
4. Live update — no "Apply" button needed

## Default Behavior

- All models pre-selected → chart shows top 5 by token count (unchanged from current behavior)
- User can type in the dropdown to search for specific models
- Clicking a model tag removes it; clicking "+" adds it back

## Edge Cases

- If user deselects all models: chart shows "No data available" or empty state
- If only 1 model remains selected: chart renders as single-series stacked bar
- Model filter is ignored when `breakdown_by == "token_type"` (no models to filter)
