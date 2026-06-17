"""OpenCode token usage data extraction from opencode.db.

Queries ~/.local/share/opencode/opencode.db directly instead of
scanning JSON files (opencode_tokens.py). Upserts into lmstudio_usage.db
via lmstudio_db.upsert_conversation().
"""
import json
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_timestamp_ms(ms_value):
    """Convert millisecond timestamp to naive datetime (UTC).

    Args:
        ms_value: Integer or float timestamp in milliseconds.

    Returns:
        datetime object (naive, UTC), or None on failure.
    """
    if ms_value is None:
        return None
    try:
        ts = int(ms_value)
        if ts > 3999999999:
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).replace(tzinfo=None)
        else:
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
    except (ValueError, OSError, OverflowError):
        return None


def _extract_tokens(data_json):
    """Extract token counts from a message data JSON dict.

    Args:
        data_json: Parsed JSON dict from the 'data' column.

    Returns:
        Tuple of (input_tokens, output_tokens, reasoning_tokens, cache_read_tokens).
    """
    tokens = data_json.get("tokens", {}) if isinstance(data_json.get("tokens"), dict) else {}
    input_tok = int(tokens.get("input", 0) or 0)
    output_tok = int(tokens.get("output", 0) or 0)
    reasoning_tok = int(tokens.get("reasoning", 0) or 0)
    cache_obj = tokens.get("cache", {}) if isinstance(tokens.get("cache"), dict) else {}
    cache_read_tok = int(cache_obj.get("read", 0) or 0)
    return input_tok, output_tok, reasoning_tok, cache_read_tok


def _row_to_conversation(row, tool_call_counts: dict | None = None):
    """Convert an opencode.db message row to a conversation dict for upsert.

    Args:
        row: Tuple (id, time_created, data_text) from the SQL query.
        tool_call_counts: Pre-computed {message_id: count} dict from batch query.

    Returns:
        Dict compatible with lmstudio_db.upsert_conversation(), or None if
        the message should be skipped (no model, zero tokens).
    """
    msg_id, time_created_ms, data_text = row

    tool_call_count = (tool_call_counts or {}).get(msg_id, 0) if msg_id else 0

    try:
        data_json = json.loads(data_text) if isinstance(data_text, str) else None
    except (json.JSONDecodeError, TypeError):
        data_json = None

    if data_json is None:
        logger.warning(f"Skipping message {msg_id}: malformed JSON in data column")
        return None

    role = data_json.get("role", "")
    if role != "assistant":
        return None

    # Extract model — assistant messages have top-level modelID
    model_name = data_json.get("modelID") or ""
    # Strip opencode-specific provider prefixes (e.g. unsloth/) to normalize
    # against LMStudio and pi model names which don't include those providers.
    if model_name.startswith("unsloth/"):
        model_name = model_name[len("unsloth/"):]
    if not model_name:
        logger.warning(f"Skipping message {msg_id}: no modelID found")
        return None

    # Extract tokens
    input_tok, output_tok, reasoning_tok, cache_read_tok = _extract_tokens(data_json)
    total_tokens = input_tok + output_tok + reasoning_tok + cache_read_tok

    if total_tokens == 0:
        return None

    created_at = _parse_timestamp_ms(time_created_ms)

    return {
        "filename": msg_id,
        "token_count": total_tokens,
        "message_count": 1,
        "model": model_name,
        "created_at": created_at,
        "user_last_message_at": created_at,
        "source": "opencode",
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "reasoning_tokens": reasoning_tok,
        "cache_read_tokens": cache_read_tok,
        "tool_call_count": tool_call_count,
    }


def sync_opencode_tokens(db_path: str | None = None, lmstudio_db_path: str | None = None) -> int:
    """Read assistant messages from opencode.db and upsert into lmstudio_usage.db.

    Queries the message table for assistant messages with non-zero token counts,
    extracts model/token data from the JSON 'data' column, and writes each
    message as a row in lmstudio_usage.db.conversations via upsert_conversation().

    Args:
        db_path: Path to opencode.db. Defaults to ~/.local/share/opencode/opencode.db.
        lmstudio_db_path: Path to lmstudio_usage.db. Defaults to data/lmstudio_usage.db.

    Returns:
        Number of conversations successfully synced.
    """
    from lmstudio_db import init_db, upsert_conversation

    if db_path is None:
        db_path = str(Path.home() / ".local" / "share" / "opencode" / "opencode.db")

    # Check if opencode.db exists
    if not Path(db_path).exists():
        logger.warning(f"opencode.db not found at {db_path}, skipping sync")
        return 0

    # SQL query: filter assistant messages with non-zero tokens
    query = """
        SELECT id, time_created, data
        FROM message
        WHERE json_extract(data, '$.role') = 'assistant'
          AND (COALESCE(json_extract(data, '$.tokens.input'), 0)
             + COALESCE(json_extract(data, '$.tokens.output'), 0)
             + COALESCE(json_extract(data, '$.tokens.reasoning'), 0)
             + COALESCE(json_extract(data, '$.tokens.cache.read'), 0)) > 0
    """

    if lmstudio_db_path is None:
        lmstudio_db_path = str(Path(__file__).parent / "data" / "lmstudio_usage.db")
    init_db(lmstudio_db_path)

    synced = 0
    skipped = 0

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = None
    except sqlite3.Error as e:
        logger.warning(f"Could not open opencode.db at {db_path}: {e}")
        return 0

    cursor = conn.cursor()
    try:
        cursor.execute(query)
        rows = cursor.fetchall()

        # Batch-count tool calls per message for efficiency
        try:
            cursor.execute("""
                SELECT message_id, COUNT(*) FROM part
                WHERE json_extract(data, '$.type') = 'tool'
                GROUP BY message_id
            """)
            tool_call_counts = {row[0]: row[1] for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            # part table doesn't exist (e.g. older opencode.db schema)
            tool_call_counts = {}

    except sqlite3.OperationalError as e:
        logger.warning(f"Query failed on opencode.db: {e}")
        conn.close()
        return 0

    for row in rows:
        conv = _row_to_conversation(row, tool_call_counts)
        if conv is None:
            skipped += 1
            continue
        try:
            upsert_conversation(lmstudio_db_path, conv)
            synced += 1
        except Exception as e:
            logger.warning(f"Failed to upsert message {row[0]}: {e}")
            skipped += 1

    conn.close()
    if skipped > 0:
        logger.info(f"Synced {synced} opencode messages, skipped {skipped}")
    else:
        logger.info(f"Synced {synced} opencode messages")

    return synced
