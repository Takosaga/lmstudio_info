"""Pi session token usage extraction from JSONL session files.

Scans ~/.pi/agent/sessions/**/*.jsonl, extracts assistant messages with
usage data, and upserts into lmstudio_usage.db via lmstudio_db.upsert_conversation().
Mirrors the opencode_db.py pattern.
"""
import glob
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _extract_tokens(usage):
    """Extract token counts from a pi message usage dict.

    Args:
        usage: Dict with keys input, output, cacheRead, cacheWrite (and optional totalTokens).

    Returns:
        Tuple of (input_tokens, output_tokens, reasoning_tokens, cache_read_tokens, cache_write_tokens).
    """
    if not isinstance(usage, dict):
        return 0, 0, 0, 0, 0

    input_tok = int(usage.get("input", 0) or 0)
    output_tok = int(usage.get("output", 0) or 0)
    reasoning_tok = 0  # Pi usage has no 'reasoning' key
    cache_read_tok = int(usage.get("cacheRead", 0) or 0)
    cache_write_tok = int(usage.get("cacheWrite", 0) or 0)
    return input_tok, output_tok, reasoning_tok, cache_read_tok, cache_write_tok


def _parse_timestamp(ts_str):
    """Parse an ISO-format timestamp string to naive UTC datetime.

    Args:
        ts_str: ISO format timestamp string (e.g. '2026-06-06T15:36:15.145Z').

    Returns:
        datetime object (naive, UTC), or None on failure.
    """
    if not ts_str:
        return None
    try:
        ts_str = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def _msg_to_conversation(line):
    """Convert a pi JSONL message line to a conversation dict for upsert.

    Args:
        line: Parsed JSON dict from a JSONL line.

    Returns:
        Dict compatible with lmstudio_db.upsert_conversation(), or None if
        the message should be skipped (not assistant, no usage, zero tokens).
    """
    if not isinstance(line, dict):
        return None

    if line.get("type") != "message":
        return None

    message = line.get("message", {})
    if not isinstance(message, dict):
        return None

    if message.get("role") != "assistant":
        return None

    usage = message.get("usage")
    if not usage or not isinstance(usage, dict):
        return None

    input_tok, output_tok, reasoning_tok, cache_read_tok, cache_write_tok = _extract_tokens(usage)
    total_tokens = input_tok + output_tok + reasoning_tok + cache_read_tok + cache_write_tok

    if total_tokens == 0:
        return None

    ts_str = line.get("timestamp")
    created_at = _parse_timestamp(ts_str)

    # Normalize model name — strip any provider prefix for cross-source merging
    model_name = (message.get("model") or "")
    model_name = re.sub(r"^[a-zA-Z][a-zA-Z0-9_-]+/", "", model_name)

    msg_id = message.get("id", "")
    if ts_str:
        safe_ts = ts_str.replace(":", "-").replace(".", "_")
        filename = f"pi_{safe_ts}_{msg_id}"
    else:
        filename = f"pi_unknown_{msg_id}"

    return {
        "filename": filename,
        "token_count": total_tokens,
        "message_count": 1,
        "model": model_name,
        "created_at": created_at,
        "user_last_message_at": created_at,
        "source": "pi",
        "input_tokens": input_tok,
        "output_tokens": output_tok,
        "reasoning_tokens": reasoning_tok,
        "cache_read_tokens": cache_read_tok,
        "cache_write_tokens": cache_write_tok,
        "tool_call_count": 0,
    }


def sync_pi_tokens(db_path=None, lmstudio_db_path=None):
    """Read assistant messages from pi JSONL session files and upsert into lmstudio_usage.db.

    Scans ~/.pi/agent/sessions/**/*.jsonl, extracts assistant messages with usage data,
    and writes each as a row in lmstudio_usage.db.conversations via upsert_conversation().

    Args:
        db_path: Base path to pi sessions directory. Defaults to ~/.pi/agent/sessions/.
        lmstudio_db_path: Path to lmstudio_usage.db. Defaults to data/lmstudio_usage.db.

    Returns:
        Number of conversations successfully synced.
    """
    from lmstudio_db import init_db, upsert_conversation

    if db_path is None:
        db_path = str(Path.home() / ".pi" / "agent" / "sessions")

    if lmstudio_db_path is None:
        lmstudio_db_path = str(Path(__file__).parent / "data" / "lmstudio_usage.db")

    if not Path(db_path).exists():
        logger.warning(f"Pi sessions directory not found at {db_path}, skipping sync")
        return 0

    init_db(lmstudio_db_path)

    synced = 0
    skipped = 0

    jsonl_files = sorted(glob.glob(str(Path(db_path) / "**" / "*.jsonl"), recursive=True))

    for jsonl_file in jsonl_files:
        try:
            with open(jsonl_file, "r") as f:
                for line_num, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed = json.loads(line)
                    except json.JSONDecodeError:
                        skipped += 1
                        continue

                    conv = _msg_to_conversation(parsed)
                    if conv is None:
                        skipped += 1
                        continue

                    try:
                        upsert_conversation(lmstudio_db_path, conv)
                        synced += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to upsert message in {jsonl_file}:{line_num}: {e}"
                        )
                        skipped += 1

        except (OSError, IOError) as e:
            logger.warning(f"Could not read JSONL file {jsonl_file}: {e}")
            continue

    if skipped > 0:
        logger.info(f"Synced {synced} pi messages, skipped {skipped}")
    else:
        logger.info(f"Synced {synced} pi messages")

    return synced
