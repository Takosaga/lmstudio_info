"""Tests for LMStudio database operations."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_database_module_imports():
    """Verify all expected functions are exported from lmstudio_db"""
    
    from lmstudio_db import init_db, get_connection, upsert_conversation
    
    assert init_db is not None
    assert get_connection is not None
    assert upsert_conversation is not None


def test_query_all_records():
    """Test querying all records from database"""
    
    import lmstudio_tokens
    
    db_path = tempfile.mktemp(suffix='.db')
    
    try:
        # Create test directory with sample data
        tmpdir = tempfile.mkdtemp()
        test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
        os.makedirs(test_dir)
        
        import json
        conv_001 = {"tokenCount": 1000, "messages": [{"role": "user", "content": "Hello"}], "modelName": "Model-A", "createdAt": 1709251200}
        conv_002 = {"tokenCount": 2000, "messages": [{"role": "user", "content": "Hi"}], "modelName": "Model-B", "createdAt": 1709345600}
        
        (test_dir / 'conv_001.json').write_text(json.dumps(conv_001))
        (test_dir / 'conv_002.json').write_text(json.dumps(conv_002))
        
        # Load and insert into database
        json_files = [str(test_dir / f) for f in os.listdir(test_dir)]
        conversations = lmstudio_tokens.load_conversations_from_files(json_files)
        
        from lmstudio_db import init_db as db_init, upsert_conversation
        
        for conv in conversations:
            conv['filename'] = conv.get('filename', 'unknown')
            upsert_conversation(db_path, conv)
        
        # Query all records
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversations")
        rows = cursor.fetchall()
        
        assert len(rows) == 2, f"Should find 2 records, found {len(rows)}"
    finally:
        os.unlink(db_path)
