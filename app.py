"""LMStudio Token Usage Dashboard — local shiny app."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_plotly


# Resolve database path relative to project root
_DB_PATH = Path(__file__).parent / "data" / "lmstudio_usage.db"

# Load data from all sources at startup (module-level)
def _load_all_sources():
    """Scan LMStudio conversations and sync OpenCode tokens, then load unified data."""
    import os
    
    # 1. Scan and upsert LMStudio conversations (only if conversations exist)
    try:
        from lmstudio_tokens import scan_conversations as ls_scan, load_conversations_from_files as ls_load
        from lmstudio_db import init_db, upsert_conversation

        json_files = ls_scan()
        if json_files:
            conversations = ls_load(json_files)
            init_db(str(_DB_PATH))
            for conv in conversations:
                conv.setdefault('source', 'lmstudio')
                upsert_conversation(str(_DB_PATH), conv)
    except Exception:
        pass  # Skip LMStudio scanning if paths don't exist

    # 2. Sync OpenCode messages from opencode.db (only if opencode.db exists)
    try:
        import opencode_db
        opencode_db.sync_opencode_tokens()
    except Exception:
        pass  # Skip OpenCode sync if path doesn't exist

    # 3. Load unified data from DB
    from data_loader import load_unified_data
    try:
        df = load_unified_data(str(_DB_PATH))
        return df if not df.empty else None
    except Exception:
        return None


df = _load_all_sources()


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

# --- UI ---
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_radio_buttons(
            "time_period",
            "Time Period",
            choices={"Monthly": "Monthly", "Daily": "Daily", "Calendar": "Calendar"},
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
    # Chart
    ui.card(
        ui.card_header("Token Usage Over Time"),
        output_widget("usage_chart"),
    ),
    ui.include_css(str(Path(__file__).parent / "assets" / "styles.css")),
    fillable=True,
)

# --- Server ---
def server(input, output, session):
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



        if data.empty:
            return data

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

    @output
    @render.text
    def total_tokens_header():
        return "Total Tokens"

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
    def avg_header():
        return "Average Daily Tokens" if input.time_period() == "Daily" else "Average Monthly Tokens"

    @output
    @render.text
    def avg_value():
        data = filtered_data()
        if data is None or data.empty:
            return "No data available."
        dt = pd.to_datetime(data["created_at"])
        if input.time_period() == "Daily":
            data["_day"] = dt.dt.date
            periods = data["_day"].nunique()
        else:
            data["_month"] = dt.dt.to_period("M")
            periods = data["_month"].nunique()
        if periods == 0:
            return "No data available."
        avg = int(data["token_count"].sum() / periods)
        return f"{avg:,}"

    @output
    @render.text
    def top_model_header():
        return "Top Model"

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

    @output
    @render_plotly()
    def usage_chart():
        data = filtered_data()
        if data is None or data.empty:
            return None

        # === CALENDAR HEATMAP MODE ===
        if input.time_period() == "Calendar":
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
                height=max(300, len(cal_data['y']) * 25),
            )

            fig.update_xaxes(type='category')
            return fig

        agg_top5 = data.copy()

        top_5_models = (
            agg_top5.groupby("model")["token_count"]
            .sum()
            .nlargest(5)
            .index.tolist()
        )
        agg_top5 = agg_top5[agg_top5["model"].isin(top_5_models)].copy()

        gran = input.time_period()
        if gran == "Monthly":
            agg_top5["_time"] = pd.to_datetime(agg_top5["created_at"]).dt.to_period("M")
        else:
            agg_top5["_time"] = pd.to_datetime(agg_top5["created_at"]).dt.date

        # Determine grouping column based on breakdown toggle
        if input.breakdown_by() == "token_type":
            # Pivot token type columns into long format for stacking
            token_cols = ['input_tokens', 'output_tokens', 'reasoning_tokens', 'cache_read_tokens']
            agg = agg_top5.groupby("_time")[token_cols].sum().reset_index()
            agg_melted = agg.melt(id_vars=['_time'], value_vars=token_cols,
                                   var_name='token_type', value_name='token_count')
            agg_melted['_time_label'] = agg_melted['_time'].apply(
                lambda x: x.strftime("%m/%d") if (hasattr(x, 'strftime') and gran == "Daily") else x.strftime("%b %Y") if hasattr(x, 'strftime') else str(x)
            )
            # Format token type names for display
            agg_melted['token_type'] = agg_melted['token_type'].map({
                'input_tokens': 'Input',
                'output_tokens': 'Output',
                'reasoning_tokens': 'Reasoning',
                'cache_read_tokens': 'Cache Read',
            })

            # Determine displayed token types (those with non-zero counts)
            displayed_types = agg_melted['token_type'].unique().tolist()
            if not displayed_types:
                return None

            # Order consistently
            type_order = ['Input', 'Output', 'Reasoning', 'Cache Read']
            type_order = [t for t in type_order if t in displayed_types]

            agg_melted['type_order'] = agg_melted['token_type'].map({t: i for i, t in enumerate(type_order)})

            palette = ['#457b9d', '#e63946', '#2a9d8f', '#f4a261']
            palette = palette[:len(type_order)]

            def _safe_pct(x):
                s = x.sum()
                return (x / s * 100).round(1) if s > 0 else 0.0

            agg_melted['_pct'] = agg_melted.groupby('_time')['token_count'].transform(_safe_pct)

            fig = px.bar(
                agg_melted,
                x='_time_label',
                y='token_count',
                color='token_type',
                color_discrete_map=dict(zip(type_order, palette)),
                barmode='stack',
                labels={'_time': 'Time', 'token_count': 'Tokens', 'token_type': 'Token Type'},
                category_orders={
                    'token_type': type_order,
                    '_time_label': agg_melted.drop_duplicates('_time')['_time_label'].tolist(),
                },
                text=agg_melted['token_count'].apply(lambda x: f"{x:,}" if x > 100 else ""),
                hover_data={
                    'token_type': True,
                    'token_count': True,
                    '_pct': ':.1f%%',
                    '_time_label': True,
                },
                custom_data=['token_type', 'token_count', '_pct'],
            )
            fig.update_traces(
                hovertemplate="<b>%{customdata[0]}</b><br>Tokens: %{customdata[1]:,}<br>Period share: %{customdata[2]}<extra></extra>",
                textposition="inside",
            )
            legend_title = "Top 5 Token Types"
        else:
            # === MODEL-BASED CHART LOGIC (unchanged from original) ===
            agg = agg_top5.groupby(["_time", "model"])["token_count"].sum().reset_index()
            if agg.empty:
                return None

            # Format time labels for display
            if gran == "Monthly":
                agg["_time_label"] = agg["_time"].dt.strftime("%b %Y")
            else:
                agg["_time_label"] = agg["_time"].astype(str)

            # Determine top 5 models from filtered data
            displayed_models = list(agg.groupby("model")["token_count"].sum().nlargest(5).index)

            # Order models consistently (largest first)
            model_order = {m: i for i, m in enumerate(displayed_models)}
            agg["model_order"] = agg["model"].map(model_order)

            # Distinct color palette
            palette = ["#2ec4b6", "#e16462", "#65a000", "#ff7f0e", "#7c3aed"]
            palette = palette[:len(displayed_models)]

            # Compute percentages for tooltips
            period_totals = agg.groupby("_time")["token_count"].transform("sum")
            agg["_pct"] = (agg["token_count"] / period_totals * 100).round(1)

            # Plotly stacked bar with hover tooltips
            fig = px.bar(
                agg,
                x="_time_label",
                y="token_count",
                color="model",
                color_discrete_map=dict(zip(displayed_models, palette)),
                barmode="stack",
                labels={"_time": "Time", "token_count": "Tokens", "model": "Model"},
                category_orders={
                    "model": [m for m, _ in sorted(model_order.items(), key=lambda x: x[1])],
                    "_time_label": agg.drop_duplicates("_time")["_time_label"].tolist(),
                },
                text=agg["token_count"].apply(lambda x: f"{x:,}" if x > 100 else ""),
                hover_data={
                    "model": True,
                    "token_count": True,
                    "_pct": ":.1f%%",
                    "_time_label": True,
                },
                custom_data=["model", "token_count", "_pct"],
            )
            fig.update_traces(
                hovertemplate="<b>%{customdata[0]}</b><br>Tokens: %{customdata[1]:,}<br>Period share: %{customdata[2]}<extra></extra>",
                textposition="inside",
            )
            # Dynamic legend title
            legend_title = f"Top {len(displayed_models)} Models" if len(displayed_models) != 5 else "Top 5 Models"

        fig.update_layout(
            xaxis_title="Time Period",
            yaxis_title="Total Tokens",
            legend_title=legend_title,
            xaxis_tickangle=-45,
            uniformtext_minsize=10,
            uniformtext_mode="hide",
            margin=dict(l=60, r=30, t=30, b=60),
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(size=12),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=1.08,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0.8)",
            ),
        )
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="LightGray")
        return fig

    # Update time_range choices based on time_period selection
    @reactive.effect
    def update_time_range_choices():
        if input.time_period() == "Daily":
            ui.update_radio_buttons(
                "time_range",
                choices={"7": "7 days", "30": "30 days", "90": "90 days"},
                selected="30",
            )
        else:
            ui.update_radio_buttons(
                "time_range",
                choices={
                    "90": "90 days",
                    "current_year": "Current Year",
                    "all": "All Time",
                },
                selected="current_year",
            )

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000, debug=True)
