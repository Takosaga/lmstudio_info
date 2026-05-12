"""OpenCode token usage data extraction.

Mirrors lmstudio_tokens.py interface but parses OpenCode's JSON message format.
Scans ~/.local/share/opencode/storage/message/**/*.json for token usage data.
"""
import json
import glob
import os
from pathlib import Path
from datetime import datetime, timezone


def scan_conversations():
    """Find all OpenCode message JSON files recursively."""
    opencode_dir = os.path.expanduser('~/.local/share/opencode/storage/message')

    if not os.path.exists(opencode_dir) or not os.path.isdir(opencode_dir):
        return []

    try:
        json_files = glob.glob(os.path.join(opencode_dir, '**', 'msg_*.json'), recursive=True)
        if isinstance(json_files, list):
            return sorted([str(Path(f).resolve()) for f in json_files])
        return []
    except Exception:
        return []


def _safe_get_nested(d, *keys, default=None):
    """Safely traverse nested dict keys."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d


def extract_from_json(file_path):
    """Parse OpenCode JSON message and extract metadata.

    Handles two JSON formats found in OpenCode storage:
    - Messages with top-level modelID/providerID fields
    - Messages with nested model object {providerID, modelID}
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        msg_data = json.load(f)

    # Use message 'id' as filename (unique per message)
    filename = msg_data.get('id', Path(file_path).name)

    # Extract model — try top-level modelID first, then nested model.modelID
    model_name = msg_data.get('modelID') or _safe_get_nested(msg_data, 'model', 'modelID', default='')
    if not model_name:
        model_name = 'unknown'

    # Extract tokens with safe defaults
    tokens_obj = msg_data.get('tokens', {}) if isinstance(msg_data.get('tokens'), dict) else {}
    input_tokens = int(tokens_obj.get('input', 0) or 0)
    output_tokens = int(tokens_obj.get('output', 0) or 0)
    reasoning_tokens = int(tokens_obj.get('reasoning', 0) or 0)
    cache_obj = tokens_obj.get('cache', {}) if isinstance(tokens_obj.get('cache'), dict) else {}
    cache_read_tokens = int(cache_obj.get('read', 0) or 0)
    total_tokens = input_tokens + output_tokens + reasoning_tokens + cache_read_tokens

    # Extract timestamp from time.created (milliseconds in OpenCode format)
    created_at = None
    ts_raw = _safe_get_nested(msg_data, 'time', 'created', default=None)
    if ts_raw is not None:
        try:
            # OpenCode timestamps are always milliseconds (> year 2100 threshold)
            if ts_raw > 3999999999:
                created_at = datetime.fromtimestamp(ts_raw / 1000, tz=timezone.utc).replace(tzinfo=None)
            else:
                created_at = datetime.fromtimestamp(ts_raw, tz=timezone.utc).replace(tzinfo=None)
        except (ValueError, OSError):
            created_at = None

    return {
        'filename': filename,
        'token_count': total_tokens,
        'message_count': 1,  # Each file is one message
        'model': model_name,
        'created_at': created_at,
        'user_last_message_at': created_at,  # Use same timestamp as fallback
        'source': 'opencode',
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'reasoning_tokens': reasoning_tokens,
        'cache_read_tokens': cache_read_tokens,
    }


def load_conversations_from_files(json_files):
    """Load conversations from list of JSON file paths."""
    conversations = []
    for json_file in json_files:
        try:
            conv_data = extract_from_json(json_file)
            conversations.append(conv_data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load {json_file}: {e}")
    return conversations


def main():
    """Main entry point for command-line usage."""
    json_files = scan_conversations()
    print(f"Found {len(json_files)} OpenCode message file(s)")

    if json_files:
        print("\nParsing messages...")
        conversations = load_conversations_from_files(json_files)
        print(f"Successfully extracted {len(conversations)} message(s)\n")

        if conversations:
            total = sum(c['token_count'] for c in conversations)
            print(f"Total tokens across all messages: {total:,}")
            models = {}
            for c in conversations:
                m = c['model'] or 'unknown'
                models[m] = models.get(m, 0) + c['token_count']
            for m, t in sorted(models.items(), key=lambda x: -x[1]):
                print(f"  {m}: {t:,} tokens")

        # Upsert conversations into database
        from lmstudio_db import init_db, upsert_conversation
        db_path = str(Path(__file__).parent / "data" / "lmstudio_usage.db")
        init_db(db_path)

        inserted = 0
        updated = 0
        for conv in conversations:
            result = upsert_conversation(db_path, conv)
            if result:
                inserted += 1
            else:
                updated += 1
        print(f"\nDatabase updated: {inserted} inserted, {updated} updated")


if __name__ == "__main__":
    main()
