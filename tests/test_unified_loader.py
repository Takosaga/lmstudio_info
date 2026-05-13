import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import tempfile
import lmstudio_db
import data_loader


def test_load_unified_data_basic():
    """Test unified data loading returns all columns."""
    db = tempfile.mktemp(suffix='.db')
    lmstudio_db.init_db(db)
    lmstudio_db.upsert_conversation(db, {
        'filename': 'test1.json', 'token_count': 100, 'message_count': 2,
        'model': 'test-model', 'source': 'lmstudio',
        'input_tokens': 50, 'output_tokens': 50, 'reasoning_tokens': 0, 'cache_read_tokens': 0,
    })
    lmstudio_db.upsert_conversation(db, {
        'filename': 'test2.json', 'token_count': 200, 'message_count': 3,
        'model': 'other-model', 'source': 'opencode',
        'input_tokens': 100, 'output_tokens': 50, 'reasoning_tokens': 30, 'cache_read_tokens': 20,
    })

    df = data_loader.load_unified_data(db)
    assert len(df) == 2
    assert set(df.columns).issuperset({'source', 'input_tokens', 'output_tokens', 'reasoning_tokens', 'cache_read_tokens'})
    assert df[df['filename'] == 'test1.json']['source'].iloc[0] == 'lmstudio'
    assert df[df['filename'] == 'test2.json']['source'].iloc[0] == 'opencode'

    import os; os.unlink(db)


def test_load_unified_data_with_date_filter():
    """Test unified data loading with date filters."""
    db = tempfile.mktemp(suffix='.db')
    lmstudio_db.init_db(db)
    lmstudio_db.upsert_conversation(db, {
        'filename': 'test1.json', 'token_count': 100, 'message_count': 2,
        'model': 'test-model', 'source': 'lmstudio',
        'input_tokens': 50, 'output_tokens': 50, 'reasoning_tokens': 0, 'cache_read_tokens': 0,
        'created_at': '2024-01-15',
    })

    df = data_loader.load_unified_data(db, start_date='2024-01-01', end_date='2024-06-01')
    assert len(df) == 1

    df_empty = data_loader.load_unified_data(db, start_date='2025-01-01')
    assert len(df_empty) == 0

    import os; os.unlink(db)


def test_load_usage_data_still_works():
    """Verify backward compatibility — load_usage_data still works with original columns."""
    db = tempfile.mktemp(suffix='.db')
    lmstudio_db.init_db(db)
    lmstudio_db.upsert_conversation(db, {
        'filename': 'test1.json', 'token_count': 100, 'message_count': 2,
        'model': 'test-model', 'source': 'lmstudio',
        'input_tokens': 50, 'output_tokens': 50, 'reasoning_tokens': 0, 'cache_read_tokens': 0,
    })

    # load_usage_data should still work (selects original columns only)
    try:
        df = data_loader.load_usage_data(db)
        assert len(df) >= 1
        assert 'token_count' in df.columns
        assert 'model' in df.columns
    finally:
        import os; os.unlink(db)
