"""Hermes Agent session token usage extraction from state.db.

Reads aggregated session data from ~/.hermes/state.db SQLite database and
upserts into lmstudio_usage.db via lmstudio_db.upsert_conversation().
Mirrors the opencode_db.py / pi_db.py pattern.
"""
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_timestamp(ts_value):
    """Convert a Unix timestamp (REAL float) to naive datetime (UTC).

    Args:
        ts_value: Unix timestamp as int or float.

    Returns:
        datetime object (naive, UTC), or None on failure.
    """
    if ts_value is None:
        return None
    try:
        dt = datetime.fromtimestamp(ts_value, tz=timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError, OSError, OverflowError):
        return None


def _row_to_conversation(row):
    """Convert a sessions table row to a conversation dict for upsert.

    Args:
        row: Tuple from SQLite cursor — (id, source, user_id, model, model_config,
             system_prompt, parent_session_id, started_at, ended_at, end_reason,
             message_count, tool_call_count, input_tokens, output_tokens,
             cache_read_tokens, cache_write_tokens, reasoning_tokens,
             billing_provider, billing_base_url, billing_mode, estimated_cost_usd,
             actual_cost_usd, cost_status, cost_source, pricing_version, title,
             api_call_count, handoff_state, handoff_platform, handoff_error,
             rewind_count, archived).

    Returns:
        Dict compatible with lmstudio_db.upsert_conversation(), or None if
        the session should be skipped (no model, zero tokens).
    """
    try:
        sid = row[0]           # id
        _source = row[1]       # source (cli, signal, telegram, etc.)
        _user_id = row[2]      # user_id
        model_name = row[3]    # model
        _model_config = row[4]  # model_config
        _system_prompt = row[5]  # system_prompt
        _parent_session_id = row[6]  # parent_session_id
        started_at = row[7]    # started_at (REAL unix timestamp)
        ended_at = row[8]      # ended_at (REAL unix timestamp)
        _end_reason = row[9]   # end_reason
        message_count = row[10]  # message_count
        tool_call_count = row[11]  # tool_call_count
        input_tokens = int(row[12] or 0)  # input_tokens
        output_tokens = int(row[13] or 0)  # output_tokens
        cache_read_tokens = int(row[14] or 0)  # cache_read_tokens
        cache_write_tokens = int(row[15] or 0)  # cache_write_tokens
        reasoning_tokens = int(row[16] or 0)  # reasoning_tokens
    except (IndexError, TypeError):
        return None

    if not model_name:
        return None

    total_tokens = input_tokens + output_tokens + reasoning_tokens + cache_read_tokens + cache_write_tokens

    if total_tokens == 0:
        return None

    # Normalize model name — strip provider/community prefix and quantization suffix for cross-source merging
    model_name = re.sub(r"^[a-zA-Z][a-zA-Z0-9_-]+/", "", model_name)
    model_name = re.sub(r"@q[0-9]_?[kx]?\w*", "", model_name)

    created_at = _parse_timestamp(started_at)
    user_last_message_at = _parse_timestamp(ended_at)

    # Session ID is the unique primary key — use directly as filename
    return {
        "filename": sid,
        "token_count": total_tokens,
        "message_count": int(message_count or 0),
        "model": model_name,
        "created_at": created_at,
        "user_last_message_at": user_last_message_at,
        "source": "hermes",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "tool_call_count": int(tool_call_count or 0),
    }


def sync_hermes_tokens(db_path=None, lmstudio_db_path=None):
    """Read sessions from Hermes state.db and upsert into lmstudio_usage.db.

    Reads aggregated token counts directly from the sessions table — no
    per-message parsing needed since Hermes stores pre-aggregated data.

    Args:
        db_path: Path to ~/.hermes/state.db. Defaults to auto-detection.
        lmstudio_db_path: Path to lmstudio_usage.db. Defaults to data/lmstudio_usage.db.

    Returns:
        Number of conversations successfully synced.
    """
    from lmstudio_db import init_db, upsert_conversation

    if db_path is None:
        db_path = str(Path.home() / ".hermes" / "state.db")

    if lmstudio_db_path is None:
        lmstudio_db_path = str(Path(__file__).parent / "data" / "lmstudio_usage.db")

    if not Path(db_path).exists():
        logger.warning(f"Hermes state.db not found at {db_path}, skipping sync")
        return 0

    init_db(lmstudio_db_path)

    synced = 0

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT id, source, user_id, model, model_config, system_prompt,
                   parent_session_id, started_at, ended_at, end_reason,
                   message_count, tool_call_count, input_tokens, output_tokens,
                   cache_read_tokens, cache_write_tokens, reasoning_tokens,
                   billing_provider, billing_base_url, billing_mode,
                   estimated_cost_usd, actual_cost_usd, cost_status,
                   cost_source, pricing_version, title, api_call_count,
                   handoff_state, handoff_platform, handoff_error,
                   rewind_count, archived
            FROM sessions
        """)

        for row in c.fetchall():
            conv = _row_to_conversation(row)
            if conv is None:
                continue
            try:
                upsert_conversation(lmstudio_db_path, conv)
                synced += 1
            except Exception as e:
                logger.warning(f"Failed to upsert session {row['id']}: {e}")

        conn.close()
    except Exception as e:
        logger.warning(f"Could not open Hermes state.db at {db_path}: {e}")
        return 0

    logger.info(f"Synced {synced} hermes sessions")
    return synced
