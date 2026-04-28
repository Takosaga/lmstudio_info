import marimo as mo

__generated_with = "0.23.2"
app = mo.App()


@app.cell
def _():
    import lmstudio_tokens

    # Find all conversation files
    json_files = lmstudio_tokens.scan_conversations()
    print(f"Found {len(json_files)} conversation file(s)")

    # Extract metadata from specific or all files
    conversations = lmstudio_tokens.load_conversations_from_files(json_files)

    for conv in conversations[:3]:  # Preview first 3
        print(f"Model: {conv['model']} | Tokens: {conv['token_count']}")
    return (conversations,)


@app.cell
def _(conversations):

    from lmstudio_db import init_db, upsert_conversation

    # Initialize database at your preferred location
    db_path = 'data/lmstudio_usage.db'

    # Extract and import

    init_db(db_path)

    for convs in conversations:
        upsert_conversation(db_path, convs)

    print(f"Imported {len(conversations)} conversation(s) to database")
    return (db_path,)


@app.cell
def _(db_path):
    from data_loader import load_usage_data, get_token_statistics, get_connection

    # Load all conversations as DataFrame
    df = load_usage_data(db_path)
    print(df.head())

    # Summary statistics
    stats = get_token_statistics(db_path)
    print(f"Total tokens: {stats['total_tokens']}")
    print(f"Conversations: {stats['conversation_count']}")
    print(f"Avg tokens/conv: {stats['avg_tokens_per_conv']:.0f}")

    # Group by model
    usage_by_model = df.groupby('model')['token_count'].sum().sort_values(ascending=False)
    print("\nTokens by Model:")
    print(usage_by_model)

    # Filter by date range (ISO format timestamps in database)
    recent_usage = load_usage_data(
        db_path, 
        start_date='2025-01-01',  # Use datetime.fromisoformat() for ISO strings
        end_date='2026-12-31'
    )
    return (df, stats, recent_usage, usage_by_model,)


@app.cell
def _(db_path, mo):
    import sqlite3
    import pandas as pd
    import os

    # Load 2026 data with error handling
    if not os.path.exists(db_path):
        chart = mo.md("Database not found. Run the import cells first.")
        dropdown = mo.null
    else:
        conn = sqlite3.connect(db_path)
        try:
            query = """
                SELECT created_at, token_count, model
                FROM conversations
                WHERE created_at >= '2026-01-01'
            """
            df_2026 = pd.read_sql_query(query, conn)
        finally:
            conn.close()

        if df_2026.empty:
            chart = mo.md("No token usage data for 2026 yet.")
            dropdown = mo.null
        else:
            # Truncate timestamps to date
            df_2026['date'] = pd.to_datetime(df_2026['created_at']).dt.date

            # Get unique models for dropdown
            models = sorted(df_2026['model'].dropna().unique().tolist())

            # Dropdown: "All models" + individual models
            dropdown_options = [('All models', '')] + [(m, m) for m in models]
            dropdown = mo.ui.dropdown(options=dropdown_options, value='', label='Model')

            # Reactive chart function
            def render_chart(selected_model):
                filtered = df_2026.copy()
                if selected_model:
                    filtered = filtered[filtered['model'] == selected_model]

                if filtered.empty:
                    return mo.md("No data for selected model.")

                daily = filtered.groupby('date')['token_count'].sum().reset_index()
                daily['date'] = pd.to_datetime(daily['date'])

                return mo.plots.bar(
                    daily,
                    x='date',
                    y='token_count',
                    title=f"Daily Token Usage{' — ' + selected_model if selected_model else ''}",
                    color='model' if not selected_model else None,
                )

            # Link dropdown to chart reactively
            chart = dropdown.output(render_chart)

    return (chart, dropdown,)


if __name__ == "__main__":
    app.run()
