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

    return (json_files,)


@app.cell
def _(json_files):
    import json

    with open(json_files[0]) as f:
        raw_data = json.load(f)
    
    print("Raw conversation structure:", list(raw_data.keys()))
    return


if __name__ == "__main__":
    app.run()
