# Dashboard Donut Chart Design Spec

## Overview

Redesign the LMStudio usage dashboard to include a donut chart showing token type breakdown (input vs output tokens) positioned to the right of stacked KPI cards.

## Layout Architecture

```
┌─────────────────────────────────────────────────────┐
│            Token Usage Over Time                    │
│                  (Bar Chart)                        │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  [Total Tokens]     [Avg Daily]     [Top Model]    │
│      Card              Card              Card       │
│                                                         │
│  ┌─────────────────────────────────────────────┐   │
│  │      [Total Tool Calls] Card                │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  (Left column: 2×2 grid, flex-grow)                 │
│                                                     │
│  ┌──────────────────────────────┐                   │
│  │   Token Type Breakdown       │                   │
│  │         Donut Chart          │                   │
│  │                              │                   │
│  └──────────────────────────────┘                   │
│               (Right column)                        │
└─────────────────────────────────────────────────────┘

            Token Usage Calendar (Heatmap)
```

**Container:** `display: flex` with two children
- Left column: 60% width, CSS Grid `2×2`, gap 20px
- Right column: 40% width, contains donut chart card

## Data Flow & Filtering

- **Source:** `filtered_data()` reactive calculation (time range filters applied)
- **Aggregation:** `groupby("token_type")["token_count"].sum()`
- **Dynamic updates:** Chart responds to sidebar filter changes (time period, time range)
- **Colors:** Same palette as bar chart (`#457b9d`, `#e63946`)
- **Tooltip:** Token count and percentage of filtered total

## Error Handling & Edge Cases

- **Empty data:** Show "No data available for selected period" placeholder.
- **Single token type:** Fallback to bar chart or show pie with single slice.
- **Zero total:** Guard against division by zero (existing pattern).

## Testing

- **Unit test:** Donut data aggregation matches filtered totals.
- **UI test:** Layout renders correctly on different screen sizes.
- **Integration test:** Chart updates when sidebar filters change.

## Implementation Details

### File to modify: `app.py`

### Changes needed:

1. **Add reactive calculation** `_donut_data()`:
   ```python
   @reactive.calc
   def donut_data():
       data = filtered_data()
       if data is None or data.empty:
           return None
       # Aggregate by token type
       agg = data.groupby("token_type")["token_count"].sum()
       return agg.to_dict()
   ```

2. **Add output function** `render_donut_chart()`:
   ```python
   @output
   @render_plotly()
   def donut_chart():
       data = donut_data()
       if not data:
           return None
       fig = px.donut(data, values=list(data.values()), labels=list(data.keys()))
       # Configure colors, tooltip, etc.
       return fig
   ```

3. **Reorganize UI** in `app_ui`:
   - Replace current card row with flex container:
     ```python
     ui.div(
         class_="dashboard-container",
         ui.div(
             class_="cards-column",
             # 4 KPI cards in 2×2 grid
         ),
         ui.div(
             class_="chart-column",
             ui.card(
                 ui.card_header("Token Type Breakdown"),
                 output_widget("donut_chart"),
             )
         )
     )
     ```

4. **Update CSS** (`assets/styles.css`):
   ```css
   .dashboard-container {
       display: flex;
       gap: 20px;
       margin-bottom: 20px;
   }
   .cards-column {
       flex: 6;
       display: grid;
       grid-template-columns: repeat(2, 1fr);
       gap: 20px;
   }
   .chart-column {
       flex: 4;
   }
   ```

## Success Criteria

- Donut chart displays token type breakdown (input/output tokens)
- Chart is positioned to the right of stacked KPI cards
- Chart updates dynamically with sidebar filters
- Layout is responsive and visually consistent

## Decisions Made

1. **Layout approach:** Flexbox/Grid for flexibility and responsiveness.
2. **Time scope:** Dynamic aggregation respecting all selected filters.
3. **Color palette:** Reuse existing bar chart colors for consistency.
