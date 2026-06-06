"""Tests for pi database module."""
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pi_db import _extract_tokens, _parse_timestamp, _msg_to_conversation


def test_extract_tokens_full():
    usage = {"input": 1000, "output": 500, "cacheRead": 200, "cacheWrite": 300, "totalTokens": 2000}
    inp, out, reason, cache_read, cache_write = _extract_tokens(usage)
    assert inp == 1000 and out == 500 and reason == 0 and cache_read == 200 and cache_write == 300


def test_extract_tokens_empty():
    inp, out, reason, cache_read, cache_write = _extract_tokens({})
    assert inp == 0 and out == 0 and reason == 0 and cache_read == 0 and cache_write == 0


def test_extract_tokens_zero_values():
    inp, out, reason, cache_read, cache_write = _extract_tokens({"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0})
    assert inp == 0 and out == 0 and reason == 0 and cache_read == 0 and cache_write == 0


def test_extract_tokens_none_input():
    inp, out, reason, cache_read, cache_write = _extract_tokens(None)
    assert inp == 0 and out == 0 and reason == 0 and cache_read == 0 and cache_write == 0


def test_parse_timestamp_iso():
    result = _parse_timestamp("2026-06-06T15:36:15.145Z")
    assert isinstance(result, datetime)


def test_parse_timestamp_none():
    result = _parse_timestamp(None)
    assert result is None


def test_msg_to_conversation_valid():
    line = {
        "type": "message",
        "timestamp": "2026-06-06T15:36:15.145Z",
        "message": {
            "role": "assistant",
            "id": "msg_001",
            "usage": {"input": 100, "output": 200, "cacheRead": 50, "cacheWrite": 10, "totalTokens": 360},
        },
    }
    result = _msg_to_conversation(line)
    assert result is not None
    assert result["source"] == "pi"
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 200
    assert result["cache_read_tokens"] == 50
    assert result["cache_write_tokens"] == 10
    assert result["token_count"] == 360


def test_msg_to_conversation_skips_user():
    line = {"type": "message", "timestamp": "2026-06-06T15:36:15.145Z", "message": {"role": "user", "content": "hello"}}
    assert _msg_to_conversation(line) is None


def test_msg_to_conversation_skips_no_usage():
    line = {"type": "message", "timestamp": "2026-06-06T15:36:15.145Z", "message": {"role": "assistant", "content": "hi"}}
    assert _msg_to_conversation(line) is None


def test_msg_to_conversation_skips_non_message():
    line = {"type": "model_change", "modelId": "gpt-4"}
    assert _msg_to_conversation(line) is None


def test_msg_to_conversation_zero_tokens_skipped():
    line = {
        "type": "message",
        "timestamp": "2026-06-06T15:36:15.145Z",
        "message": {"role": "assistant", "usage": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}},
    }
    assert _msg_to_conversation(line) is None


def test_msg_to_conversation_missing_message_key():
    line = {"type": "session", "id": "abc123"}
    assert _msg_to_conversation(line) is None
