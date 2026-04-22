"""Tests for data loader module."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd


def test_load_usage_data_import():
    """Verify load_usage_data function can be imported from data_loader"""
    try:
        from data_loader import load_usage_data, get_connection
        print("✓ Data loader module imports successfully")
    except ImportError as e:
        print(f"✗ Data loader module import failed: {e}")
        raise


def test_load_usage_data():
    """Test loading all conversations into DataFrame"""
    from data_loader import load_usage_data
    
    db_path = tempfile.mktemp(suffix='.db')
    
    try:
        import lmstudio_tokens
        
        # Create test directory with sample data
        tmpdir = tempfile.mkdtemp()
        test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
        os.makedirs(test_dir)
        
        import json
        conv_data = [
            {"tokenCount": 1000, "messages": [{"role": "user", "content": "Hello"}], "modelName": "Model-A", "createdAt": 1709251200},
            {"tokenCount": 2000, "messages": [{"role": "user", "content": "Hi"}], "modelName": "Model-B", "createdAt": 1709345600}
        ]
        
        (test_dir / 'conv_001.json').write_text(json.dumps(conv_data[0]))
        (test_dir / 'conv_002.json').write_text(json.dumps(conv_data[1]))
        
        # Load, insert into DB and test data loading
        json_files = [str(test_dir / f) for f in os.listdir(test_dir)]
        conversations = lmstudio_tokens.load_conversations_from_files(json_files)
        
        from lmstudio_db import init_db, upsert_conversation
        
        db_init = lambda p: (lambda c: None)(None).__call__ if False else init_db
        
        init_db(db_path)
        
        for conv in conversations:
            conv['filename'] = conv.get('filename', 'unknown')
            upsert_conversation(db_path, conv)
        
        # Load data as DataFrame
        df = load_usage_data(db_path)
        
        assert df is not None
        assert len(df) == 2, f"Should find 2 records, found {len(df)}"
    finally:
        os.unlink(db_path)


def test_load_nonexistent_db():
    """Test loading from database with no table raises proper error"""
    from data_loader import load_usage_data
    
    # Create an empty database file (no tables)
    db_path = tempfile.mktemp(suffix='.db')
    
    try:
        # Should raise FileNotFoundError for missing table
        df = load_usage_data(db_path)
        
        # If we get here, should be None or something unexpected
        assert False, "Should have raised an error for empty database"
    except (FileNotFoundError, pd.errors.DatabaseError):
        # Either is acceptable - file doesn't exist or table missing
        pass


def test_database_connection():
    """Test that database connection helper works"""
    from data_loader import get_connection
    
    db_path = tempfile.mktemp(suffix='.db')
    
    try:
        # Create the file first (sqlite3.connect() needs it to exist if we're being explicit)
        open(db_path, 'w').close()
        
        # Test basic connection - should succeed for empty DB
        conn = get_connection(db_path)
        assert conn is not None
        print("✓ Database connection works")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        raise
    finally:
        os.unlink(db_path) if os.path.exists(db_path) else None


def test_load_empty_database():
    """Test loading from empty database file"""
    from data_loader import load_usage_data
    
    db_path = tempfile.mktemp(suffix='.db')
    
    try:
        # Create an empty DB file
        open(db_path, 'w').close()
        
        # Should raise error for missing table
        df = load_usage_data(db_path)
        assert False, "Should have raised error"
    except (FileNotFoundError, pd.errors.DatabaseError):
        pass
    finally:
        os.unlink(db_path) if os.path.exists(db_path) else None


def test_load_with_real_data():
    """Test loading actual LMStudio data"""
    from data_loader import load_usage_data
    
    # Load the real conversation files we created earlier
    conversations_dir = Path.home() / '.lmstudio' / 'conversations'
    
    if not os.path.exists(conversations_dir):
        print("No LMStudio data found for testing")
        return
        
    # Try to connect to existing DB or create one
    db_path = tempfile.mktemp(suffix='.db')
    
    try:
        import lmstudio_tokens
        from lmstudio_db import init_db, upsert_conversation
        
        # Init and load real data
        init_db(db_path)
        
        json_files = sorted([str(f) for f in conversations_dir.glob('*.json')])[:5]  # Limit to first 5
        
        if not json_files:
            print("No JSON files found")
            return
            
        conversations = lmstudio_tokens.load_conversations_from_files(json_files[:1])
        
        for conv in conversations:
            conv['filename'] = conv.get('filename', 'unknown')
            upsert_conversation(db_path, conv)
        
        # Load the data
        df = load_usage_data(db_path)
        
        assert len(df) > 0 if df is not None else False
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_get_token_statistics():
    """Test getting token statistics"""
    from data_loader import get_token_statistics
    
    db_path = tempfile.mktemp(suffix='.db')
    
    try:
        import lmstudio_tokens
        from lmstudio_db import init_db, upsert_conversation
        
        # Create and populate DB
        tmpdir = tempfile.mkdtemp()
        test_dir = Path(tmpdir) / '.lmstudio' / 'conversations'
        os.makedirs(test_dir)
        
        import json
        conv_data = {"tokenCount": 1000, "messages": [{"role": "user", "content": "Hello"}], "modelName": "Model-A", "createdAt": 1709251200}
        
        (test_dir / 'conv_001.json').write_text(json.dumps(conv_data))
        
        json_files = [str(test_dir / f) for f in os.listdir(test_dir)]
        conversations = lmstudio_tokens.load_conversations_from_files(json_files)
        
        init_db(db_path)
        
        for conv in conversations:
            conv['filename'] = conv.get('filename', 'unknown')
            upsert_conversation(db_path, conv)
        
        # Get statistics
        stats = get_token_statistics(db_path)
        
        assert stats is not None
        assert stats['total_tokens'] > 0
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
