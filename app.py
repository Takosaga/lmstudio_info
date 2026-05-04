"""LMStudio Token Usage Dashboard — local shiny app."""

from pathlib import Path

import pandas as pd
import plotly.express as px
from shiny import App, ui, render
from shiny.types import WarnOnExpr

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
            6,
            ui.card(
                ui.card_header("Total Tokens"),
                ui.output_text("total_tokens", width="100%"),
                class_="text-center",
            ),
        ),
        ui.column(
            6,
            ui.card(
                ui.card_header("Average Monthly Tokens"),
                ui.output_text("avg_monthly", width="100%"),
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
            ui.input_select("model_filter", "Model", choices=["All models"]),
        ),
    ),
    # Chart
    ui.card(
        ui.card_header("Token Usage Over Time"),
        ui.output_plot("usage_chart"),
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
    @render.plot
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
        # Plotly stacked bar
        fig = px.bar(
            agg,
            x="_time",
            y="token_count",
            color="model",
            barmode="stack",
            labels={"_time": "Time", "token_count": "Tokens", "model": "Model"},
        )
        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Tokens",
            legend_title="Model",
            xaxis_tickangle=-45,
        )
        return fig

    # Update model filter options reactively
    @ui.effect
    def update_model_options():
        if df is None:
            return
        models = sorted(df["model"].dropna().unique().tolist())
        choices = [("All models", "")] + [(m, m) for m in models]
        ui.update_select("model_filter", choices=choices)

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000, debug=True)
