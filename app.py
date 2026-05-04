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
        class_="justify-content-center mb-4 kpi-row",
    ),
    # Chart
    ui.card(
        ui.card_header("Token Usage Over Time"),
        output_widget("usage_chart"),
    ),
    ui.include_css("assets/styles.css"),
    title="LMStudio Token Usage",
    fillable=True,
)

# --- Server ---
def server(input, output, session):
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

    @output
    @render_plotly()
    def usage_chart():
        data = filtered_data()
        if data is None or data.empty:
            return None
        filtered = data.copy()
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
        # Time Period (granularity)
        gran = input.time_period()
        if gran == "Monthly":
            agg_top5["_time"] = pd.to_datetime(agg_top5["created_at"]).dt.to_period("M").astype(str)
        else:
            agg_top5["_time"] = pd.to_datetime(agg_top5["created_at"]).dt.date.astype(str)
        # Aggregate
        agg = agg_top5.groupby(["_time", "model"])["token_count"].sum().reset_index()
        if agg.empty:
            return None

        # Determine which models are displayed
        if model == "Top 5 Models":
            displayed_models = list(agg.groupby("model")["token_count"].sum().nlargest(5).index)
        elif model:
            displayed_models = [model]
        else:
            displayed_models = list(agg["model"].unique())

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
            x="_time",
            y="token_count",
            color="model",
            color_discrete_map=dict(zip(displayed_models, palette)),
            barmode="stack",
            labels={"_time": "Time", "token_count": "Tokens", "model": "Model"},
            category_orders={"model": [m for m, _ in sorted(model_order.items(), key=lambda x: x[1])]},
            text=agg["token_count"].apply(lambda x: f"{x:,}" if x > 100 else ""),
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
        # Dynamic legend title
        legend_title = "Top 5 Models" if model == "Top 5 Models" else "Model"
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

    # Update model filter options reactively
    @reactive.effect
    def update_model_options():
        if df is None:
            return
        models = sorted(df["model"].dropna().unique().tolist())
        choices = {"": "Top 5 Models"}
        for m in models:
            choices[m] = m
        ui.update_select("model_filter", choices=choices, selected="")

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000, debug=True)
