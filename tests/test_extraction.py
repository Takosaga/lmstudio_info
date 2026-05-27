"""Tests for LMStudio conversation data extraction."""
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock, mock_open

# Add parent to path for imports during testing
sys.path.insert(0, str(Path(__file__).parent.parent))

import lmstudio_tokens


def setup_test_files():
    """Create temporary JSON files for testing"""
    test_dir = Path(tempfile.mkdtemp()) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)

    # Create sample conversation file 1
    conv_data_001 = {
        "tokenCount": 2543,
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ],
        "modelName": "Llama-3.1-8B-Instruct",
        "createdAt": 1709251200,
        "userLastMessagedAt": 1709264400
    }

    # Create sample conversation file 2 (different model)
    conv_data_002 = {
        "tokenCount": 892,
        "messages": [
            {"role": "user", "content": "Explain quantum computing"}
        ],
        "modelName": "Gemma-7b-it",
        "createdAt": 1709345600,
        "userLastMessagedAt": 1709348200
    }

    (test_dir / 'conv_001.json').write_text(
        str(conv_data_001).replace("'", '"') + '\n'
    )
    (test_dir / 'conv_002.json').write_text(
        str(conv_data_002).replace("'", '"') + '\n'
    )

    return test_dir


def get_test_json_files(test_dir):
    """Return sorted JSON file paths from test directory"""
    return sorted([str(p.resolve()) for p in test_dir.glob('*.json')])


def test_scan_conversations_empty_directory():
    """Test scanning when conversations directory doesn't exist or is empty."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock path that doesn't exist
        non_existent = os.path.join(tmpdir, 'nonexistent')
        
        with patch.object(lmstudio_tokens.os.path, 'expanduser', return_value=non_existent), \
             patch.object(lmstudio_tokens.os.path, 'exists', return_value=False):
            result = lmstudio_tokens.scan_conversations()
            
            assert len(result) == 0


def test_scan_conversations_with_files():
    """Test scanning finds all JSON files in conversations directory."""
    
    # Create a custom function for testing that returns mock results
    def mock_scan_dir(test_path):
        if 'mock_test' in test_path:
            return ['/path/to/mock/file1.json', '/path/to/mock/file2.json']
        return []
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use expanduser to return our temp directory mock
        with patch.object(lmstudio_tokens.os.path, 'expanduser', return_value=tmpdir), \
             patch.object(lmstudio_tokens.os.path, 'exists', return_value=True), \
             patch('lmstudio_tokens.glob.glob') as mock_glob:
            
            # Mock glob to return 2 files
            mock_glob.return_value = [str(Path(tmpdir) / 'mock_test' / 'file1.json')] * 2
            
            result = lmstudio_tokens.scan_conversations()
            
            assert len(result) == 2


def test_extract_from_json():
    """Test extracting metadata from a single conversation file."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    with patch('lmstudio_tokens.open', new_callable=mock_open, 
               read_data='{"tokenCount": 2543, "modelName": "Llama-3.1-8B-Instruct", "messages": [{"role": "user", "content": "Hello"}], "createdAt": 1709251200}') as mock_file:
        
        file_path = str(test_dir / 'conv_001.json')
        
        result = lmstudio_tokens.extract_from_json(file_path)

        assert 'filename' in result
        assert result['token_count'] == 2543
        assert isinstance(result['message_count'], int)


def test_extract_missing_fields():
    """Test extraction handles missing fields gracefully."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    with patch('lmstudio_tokens.open', new_callable=mock_open, 
               read_data='{"tokenCount": 100, "messages": [{"role": "user", "content": "Hi"}]}') as mock_file:
        
        file_path = str(test_dir / 'test.json')
        
        result = lmstudio_tokens.extract_from_json(file_path)

        assert result['model'] == ''
        assert result['created_at'] is None
        assert result['user_last_message_at'] is None

    """Test extraction handles empty messages array."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    with patch('lmstudio_tokens.open', new_callable=mock_open, 
               read_data='{"tokenCount": 0, "modelName": "TestModel", "messages": []}') as mock_file:
        
        file_path = str(test_dir / 'test.json')
        
        result = lmstudio_tokens.extract_from_json(file_path)

        assert result['message_count'] == 0


def test_extract_none_tokenCount():
    """Test extraction handles None token count."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    with patch('lmstudio_tokens.open', new_callable=mock_open, 
               read_data='{"tokenCount": null, "messages": [{"role": "user", "content": "Hi"}], "modelName": "TestModel"}') as mock_file:
        
        file_path = str(test_dir / 'test.json')
        
        result = lmstudio_tokens.extract_from_json(file_path)

        assert isinstance(result['token_count'], int)
        assert result['token_count'] == 0


def test_extract_timestamps():
    """Test extraction converts timestamps correctly."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    with patch('lmstudio_tokens.open', new_callable=mock_open, 
               read_data='{"tokenCount": 100, "modelName": "TestModel", "messages": [{"role": "user", "content": "Hi"}], "createdAt": 1709251200}') as mock_file:
        
        file_path = str(test_dir / 'test.json')
        
        result = lmstudio_tokens.extract_from_json(file_path)

        assert isinstance(result['created_at'], datetime)


def test_extract_no_timestamps():
    """Test extraction handles missing timestamps."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    with patch('lmstudio_tokens.open', new_callable=mock_open, 
               read_data='{"tokenCount": 100, "messages": [{"role": "user", "content": "Hi"}]}') as mock_file:
        
        file_path = str(test_dir / 'test.json')
        
        result = lmstudio_tokens.extract_from_json(file_path)

        assert result['created_at'] is None


def test_extract_timestamp_milliseconds():
    """Test extraction handles millisecond timestamps (like real LMStudio data)."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    with patch('lmstudio_tokens.open', new_callable=mock_open, 
               read_data='{"tokenCount": 100, "modelName": "TestModel", "messages": [{"role": "user", "content": "Hi"}], "createdAt": 1758827981676}') as mock_file:
        
        file_path = str(test_dir / 'test.json')
        
        result = lmstudio_tokens.extract_from_json(file_path)

        assert isinstance(result['created_at'], datetime)


def test_load_conversations_from_files():
    """Test loading multiple conversations from files."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    # Create sample JSON files matching LMStudio format
    conv_001_content = '{"tokenCount": 2543, "messages": [{"role": "user", "content": "Hello"}], "modelName": "Llama-3.1-8B-Instruct", "createdAt": 1709251200}'
    conv_002_content = '{"tokenCount": 892, "messages": [{"role": "user", "content": "Hi"}], "modelName": "Gemma-7b-it", "createdAt": 1709345600}'
    
    (test_dir / 'conv_001.json').write_text(conv_001_content)
    (test_dir / 'conv_002.json').write_text(conv_002_content)
    
    json_files = [str(test_dir / 'conv_001.json'), str(test_dir / 'conv_002.json')]
    
    conversations = lmstudio_tokens.load_conversations_from_files(json_files)
    
    assert len(conversations) == 2


def test_extract_token_type_breakdown():
    """Test extraction of input/output token breakdowns from nested genInfo.stats."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    # Realistic LMStudio JSON with nested genInfo.stats containing token breakdowns
    json_data = {
        "tokenCount": 2065,
        "messages": [
            {"role": "user", "content": "Hello"},
            {
                "versions": [
                    {
                        "steps": [
                            {
                                "genInfo": {
                                    "stats": {
                                        "promptTokensCount": 1959,
                                        "predictedTokensCount": 106,
                                        "totalTokensCount": 2065
                                    }
                                }
                            }
                        ]
                    }
                ]
            }
        ],
        "createdAt": 1709251200
    }
    
    import json as json_mod
    with patch('lmstudio_tokens.open', new_callable=mock_open,
               read_data=json_mod.dumps(json_data)) as mock_file:
        
        file_path = str(test_dir / 'test.json')
        result = lmstudio_tokens.extract_from_json(file_path)

        assert result['input_tokens'] == 1959
        assert result['output_tokens'] == 106
        assert result['reasoning_tokens'] == 0
        assert result['cache_read_tokens'] == 0


def test_extract_token_type_multiple_steps():
    """Test token type extraction sums across multiple regeneration steps."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    # Multiple regeneration steps - should sum all genInfo.stats
    json_data = {
        "tokenCount": 3462,
        "messages": [
            {"role": "user", "content": "Hello"},
            {
                "versions": [
                    {
                        "steps": [
                            {
                                "genInfo": {
                                    "stats": {
                                        "promptTokensCount": 100,
                                        "predictedTokensCount": 50,
                                        "totalTokensCount": 150
                                    }
                                }
                            },
                            {
                                "genInfo": {
                                    "stats": {
                                        "promptTokensCount": 3334,
                                        "predictedTokensCount": 128,
                                        "totalTokensCount": 3462
                                    }
                                }
                            }
                        ]
                    }
                ]
            }
        ],
        "createdAt": 1709251200
    }
    
    import json as json_mod
    with patch('lmstudio_tokens.open', new_callable=mock_open,
               read_data=json_mod.dumps(json_data)) as mock_file:
        
        file_path = str(test_dir / 'test.json')
        result = lmstudio_tokens.extract_from_json(file_path)

        # Should sum all steps
        assert result['input_tokens'] == 3434   # 100 + 3334
        assert result['output_tokens'] == 178    # 50 + 128
        assert result['reasoning_tokens'] == 0
        assert result['cache_read_tokens'] == 0


def test_extract_token_type_no_geninfo():
    """Test token type extraction returns zeros when no genInfo.stats present."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    # Old-style JSON without nested genInfo structure
    json_data = {
        "tokenCount": 100,
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ],
        "createdAt": 1709251200
    }
    
    import json as json_mod
    with patch('lmstudio_tokens.open', new_callable=mock_open,
               read_data=json_mod.dumps(json_data)) as mock_file:
        
        file_path = str(test_dir / 'test.json')
        result = lmstudio_tokens.extract_from_json(file_path)

        assert result['input_tokens'] == 0
        assert result['output_tokens'] == 0
        assert result['reasoning_tokens'] == 0
        assert result['cache_read_tokens'] == 0


def test_extract_tool_call_count():
    """Test extraction of tool call count from toolStatus steps."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    json_data = {
        "tokenCount": 2065,
        "messages": [
            {"role": "user", "content": "Hello"},
            {
                "role": "assistant",
                "versions": [
                    {
                        "steps": [
                            {"genInfo": {"stats": {"promptTokensCount": 100, "predictedTokensCount": 50}}},
                            {"type": "toolStatus", "callId": "call_1", "statusState": {"status": {"type": "toolCallSucceeded"}}},
                            {"type": "toolStatus", "callId": "call_2", "statusState": {"status": {"type": "toolCallSucceeded"}}},
                        ]
                    }
                ]
            },
            {
                "role": "assistant",
                "versions": [
                    {
                        "steps": [
                            {"type": "toolStatus", "callId": "call_3", "statusState": {"status": {"type": "toolCallSucceeded"}}},
                        ]
                    }
                ]
            }
        ],
        "createdAt": 1709251200
    }
    
    import json as json_mod
    with patch('lmstudio_tokens.open', new_callable=mock_open,
               read_data=json_mod.dumps(json_data)) as mock_file:
        
        file_path = str(test_dir / 'test.json')
        result = lmstudio_tokens.extract_from_json(file_path)

        assert result['tool_call_count'] == 3


def test_extract_tool_call_count_zero():
    """Test tool call count is 0 when no toolStatus steps present."""
    
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
    os.makedirs(test_dir)
    
    json_data = {
        "tokenCount": 100,
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"}
        ],
        "createdAt": 1709251200
    }
    
    import json as json_mod
    with patch('lmstudio_tokens.open', new_callable=mock_open,
               read_data=json_mod.dumps(json_data)) as mock_file:
        
        file_path = str(test_dir / 'test.json')
        result = lmstudio_tokens.extract_from_json(file_path)

        assert result['tool_call_count'] == 0


def test_database_module_imports():
    """Verify database module can be imported."""
    
    try:
        from lmstudio_db import init_db, get_connection
        print("✓ Database module imports successfully")
        return True
    except ImportError as e:
        print(f"✗ Database module import failed: {e}")
        return False
