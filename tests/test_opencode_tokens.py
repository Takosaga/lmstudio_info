import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open

sys.path.insert(0, str(Path(__file__).parent.parent))

import opencode_tokens


def test_extract_from_json_with_tokens():
    """Test extracting token counts from an OpenCode message with tokens."""
    json_content = '''{
        "id": "msg_test123",
        "sessionID": "ses_abc",
        "role": "assistant",
        "time": {"created": 1764334238483},
        "modelID": "big-pickle",
        "providerID": "opencode",
        "tokens": {
            "input": 94,
            "output": 48,
            "reasoning": 0,
            "cache": {"read": 10560, "write": 0}
        }
    }'''

    with patch('opencode_tokens.open', new_callable=mock_open, read_data=json_content):
        result = opencode_tokens.extract_from_json('/tmp/test_msg.json')

    assert result['filename'] == 'msg_test123'
    assert result['token_count'] == 94 + 48 + 0 + 10560  # = 10702
    assert result['input_tokens'] == 94
    assert result['output_tokens'] == 48
    assert result['reasoning_tokens'] == 0
    assert result['cache_read_tokens'] == 10560
    assert result['source'] == 'opencode'
    assert result['model'] == 'big-pickle'
    assert isinstance(result['created_at'], datetime)


def test_extract_from_json_no_tokens():
    """Test extraction handles messages without tokens (all zeros)."""
    json_content = '''{
        "id": "msg_notoke",
        "sessionID": "ses_abc",
        "role": "user",
        "time": {"created": 1766612341074},
        "model": {"providerID": "lmstudio", "modelID": "openai/gpt-oss-20b"}
    }'''

    with patch('opencode_tokens.open', new_callable=mock_open, read_data=json_content):
        result = opencode_tokens.extract_from_json('/tmp/test_msg.json')

    assert result['filename'] == 'msg_notoke'
    assert result['token_count'] == 0
    assert result['input_tokens'] == 0
    assert result['output_tokens'] == 0
    assert result['reasoning_tokens'] == 0
    assert result['cache_read_tokens'] == 0
    assert result['model'] == 'openai/gpt-oss-20b'


def test_extract_from_json_missing_model():
    """Test extraction defaults model to 'unknown' when no model info present."""
    json_content = '''{
        "id": "msg_nomodel",
        "sessionID": "ses_abc",
        "role": "assistant",
        "time": {"created": 1766612341074},
        "tokens": {"input": 10, "output": 5, "reasoning": 0, "cache": {"read": 0, "write": 0}}
    }'''

    with patch('opencode_tokens.open', new_callable=mock_open, read_data=json_content):
        result = opencode_tokens.extract_from_json('/tmp/test_msg.json')

    assert result['model'] == 'unknown'


def test_scan_conversations_empty():
    """Test scanning when OpenCode directory doesn't exist."""
    with patch('opencode_tokens.os.path.expanduser', return_value='/nonexistent/path'), \
         patch('opencode_tokens.os.path.exists', return_value=False):
        result = opencode_tokens.scan_conversations()
    assert result == []


def test_scan_conversations_finds_files():
    """Test scanning finds all msg_*.json files recursively."""
    tmpdir = tempfile.mkdtemp()

    # Create session dirs and message files
    (Path(tmpdir) / 'ses_1').mkdir()
    (Path(tmpdir) / 'ses_2').mkdir()
    (Path(tmpdir) / 'ses_1' / 'msg_a.json').write_text('{}')
    (Path(tmpdir) / 'ses_2' / 'msg_b.json').write_text('{}')

    with patch('opencode_tokens.os.path.expanduser', return_value=tmpdir), \
         patch('opencode_tokens.os.path.exists', return_value=True):
        result = opencode_tokens.scan_conversations()

    assert len(result) == 2


def test_load_conversations_from_files():
    """Test loading multiple OpenCode conversations."""
    tmpdir = tempfile.mkdtemp()
    session_dir = Path(tmpdir) / 'ses_test'
    session_dir.mkdir()

    msg1 = '{"id": "msg_1", "time": {"created": 1764334238483}, "modelID": "test-model", "tokens": {"input": 10, "output": 5, "reasoning": 0, "cache": {"read": 100, "write": 0}}}'
    msg2 = '{"id": "msg_2", "time": {"created": 1764334239000}, "modelID": "test-model", "tokens": {"input": 20, "output": 10, "reasoning": 0, "cache": {"read": 200, "write": 0}}}'

    (session_dir / 'msg_1.json').write_text(msg1)
    (session_dir / 'msg_2.json').write_text(msg2)

    json_files = [str(session_dir / 'msg_1.json'), str(session_dir / 'msg_2.json')]
    conversations = opencode_tokens.load_conversations_from_files(json_files)

    assert len(conversations) == 2
    assert conversations[0]['token_count'] == 10 + 5 + 0 + 100  # = 115
    assert conversations[1]['token_count'] == 20 + 10 + 0 + 200  # = 230


def test_load_handles_invalid_json():
    """Test that invalid JSON files are skipped with a warning."""
    tmpdir = tempfile.mkdtemp()
    session_dir = Path(tmpdir) / 'ses_test'
    session_dir.mkdir()

    (session_dir / 'msg_bad.json').write_text('not valid json{{{')
    (session_dir / 'msg_good.json').write_text(
        '{"id": "msg_good", "time": {"created": 1764334238483}, "modelID": "test", "tokens": {"input": 1, "output": 1, "reasoning": 0, "cache": {"read": 0, "write": 0}}}'
    )

    json_files = [str(session_dir / 'msg_bad.json'), str(session_dir / 'msg_good.json')]
    conversations = opencode_tokens.load_conversations_from_files(json_files)

    assert len(conversations) == 1
    assert conversations[0]['filename'] == 'msg_good'
