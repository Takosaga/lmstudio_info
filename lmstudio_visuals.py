import marimo

__generated_with = "0.23.2"
app = marimo.App()


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
    stats = get_token_statistics()
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
    return


if __name__ == "__main__":
    app.run()
