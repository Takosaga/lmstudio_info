"""LMStudio Token Usage Dashboard — local shiny app."""

from pathlib import Path

import pandas as pd
import plotly.express as px
from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_plotly


# Resolve database path relative to project root
_DB_PATH = Path(__file__).parent / "data" / "lmstudio_usage.db"

# Load data once at startup
def _load_data():
    """Load conversation data from the database."""
    if not _DB_PATH.exists():
        return None
    from data_loader import load_usage_data
    try:
        df = load_usage_data(str(_DB_PATH))
        if df.empty:
            return None
        return df
    except Exception:
        return None

# Load data before app starts (module-level)
df = _load_data()

# --- UI ---
app_ui = ui.page_fluid(
    ui.h2("LMStudio Token Usage", class_="text-center mb-4"),
    # Summary cards row
    ui.row(
        ui.column(
            4,
            ui.card(
                ui.card_header("Total Tokens"),
                ui.output_text("total_tokens"),
                class_="text-center",
            ),
        ),
        ui.column(
            4,
            ui.card(
                ui.card_header("Average Monthly Tokens"),
                ui.output_text("avg_monthly"),
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
    ),
    # Controls
    ui.row(
        ui.column(
            4,
            ui.input_select("granularity", "Granularity", choices=["Daily", "Monthly"]),
        ),
        ui.column(
            4,
            ui.input_select("model_filter", "Model", choices={"": "All models"}),
        ),
    ),
    # Chart
    ui.card(
        ui.card_header("Token Usage Over Time — Top 5 Models"),
        output_widget("usage_chart"),
    ),
)

# --- Server ---
def server(input, output, session):
    @output
    @render.text
    def total_tokens():
        if df is None:
            return "No data available."
        total = int(df["token_count"].sum())
        return f"{total:,}"

    @output
    @render.text
    def avg_monthly():
        if df is None:
            return "No data available."
        df_copy = df.copy()
        df_copy["_month"] = pd.to_datetime(df_copy["created_at"]).dt.to_period("M")
        months = df_copy["_month"].nunique()
        if months == 0:
            return "No data available."
        avg = int(df["token_count"].sum() / months)
        return f"{avg:,}"

    @output
    @render.text
    def top_model():
        if df is None:
            return "No data available."
        model_usage = df.groupby("model")["token_count"].sum().sort_values(ascending=False)
        if model_usage.empty:
            return "No data available."
        top = model_usage.index[0]
        tokens = int(model_usage.iloc[0])
        return f"{top}\n{tokens:,} tokens"

    @output
    @render_plotly()
    def usage_chart():
        if df is None:
            return None
        filtered = df.copy()
        # Model filter
        model = input.model_filter()
        if model and model != "All models":
            models_list = list(filtered["model"].dropna().unique())
            if model in models_list:
                filtered = filtered[filtered["model"] == model]
        # Granularity
        gran = input.granularity()
        if gran == "Monthly":
            filtered["_time"] = pd.to_datetime(filtered["created_at"]).dt.to_period("M").astype(str)
        else:
            filtered["_time"] = pd.to_datetime(filtered["created_at"]).dt.date.astype(str)
        # Aggregate
        agg = filtered.groupby(["_time", "model"])["token_count"].sum().reset_index()
        if agg.empty:
            return None

        # Top 5 models by total token count
        top_5_models = (
            agg.groupby("model")["token_count"]
            .sum()
            .nlargest(5)
            .index.tolist()
        )
        agg_top5 = agg[agg["model"].isin(top_5_models)]

        # Order models consistently (largest first)
        model_order = {m: i for i, m in enumerate(top_5_models)}
        agg_top5["model_order"] = agg_top5["model"].map(model_order)

        # Distinct color palette
        palette = ["#2ec4b6", "#e16462", "#65a000", "#ff7f0e", "#7c3aed"]
        palette = palette[:len(top_5_models)]

        # Compute percentages for tooltips
        period_totals = agg_top5.groupby("_time")["token_count"].transform("sum")
        agg_top5["_pct"] = (agg_top5["token_count"] / period_totals * 100).round(1)

        # Plotly stacked bar with hover tooltips
        fig = px.bar(
            agg_top5,
            x="_time",
            y="token_count",
            color="model",
            color_discrete_map=dict(zip(top_5_models, palette)),
            barmode="stack",
            labels={"_time": "Time", "token_count": "Tokens", "model": "Model"},
            category_orders={"model": [m for m, _ in sorted(model_order.items(), key=lambda x: x[1])]},
            text=agg_top5["token_count"].apply(lambda x: f"{x:,}" if x > 100 else ""),
            hover_data={
                "model": True,
                "token_count": True,
                "_pct": ":.1f%%",
                "_time": True,
            },
            custom_data=["model", "token_count", "_pct"],
        )
        fig.update_traces(
            hovertemplate="<b>%{customdata[0]}</b><br>Tokens: %{customdata[1]:,}<br>Period share: %{customdata[2]}<extra></extra>",
            textposition="inside",
        )
        fig.update_layout(
            xaxis_title="Time Period",
            yaxis_title="Total Tokens",
            legend_title="Top 5 Models",
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

    # Update model filter options reactively
    @reactive.effect
    def update_model_options():
        if df is None:
            return
        models = sorted(df["model"].dropna().unique().tolist())
        choices = {"": "All models"}
        for m in models:
            choices[m] = m
        ui.update_select("model_filter", choices=choices)

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000, debug=True)
