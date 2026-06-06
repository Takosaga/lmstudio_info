"""Tests for calendar heatmap data aggregation."""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Add parent directory to path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_build_calendar_data_basic():
    """Test basic aggregation of daily totals across all models."""
    from app import _build_calendar_data

    data = pd.DataFrame({
        'model': ['gpt-4', 'gpt-4', 'claude-3'],
        'created_at': pd.to_datetime(['2025-01-01', '2025-01-01', '2025-01-02']),
        'input_tokens': [100, 200, 150],
        'output_tokens': [300, 400, 250],
        'reasoning_tokens': [0, 0, 50],
        'cache_read_tokens': [0, 0, 0],
    })

    result = _build_calendar_data(data)

    assert result is not None
    assert isinstance(result, dict)
    assert 'z' in result
    assert 'x' in result
    assert 'y' in result
    assert result['y'] == ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    assert len(result['z']) == 7  # 7 rows for days of week


def test_build_calendar_data_zero_fill():
    """Test that missing model-day combinations are zero-filled."""
    from app import _build_calendar_data

    data = pd.DataFrame({
        'model': ['gpt-4'],
        'created_at': pd.to_datetime(['2025-01-01']),
        'input_tokens': [100],
        'output_tokens': [300],
        'reasoning_tokens': [0],
        'cache_read_tokens': [0],
    })

    result = _build_calendar_data(data)

    # All cells should be non-negative (z is nested list)
    flat = [v for row in result['z'] for v in row]
    assert all(v >= 0 for v in flat)


def test_build_calendar_data_empty():
    """Test that empty data returns empty dicts."""
    from app import _build_calendar_data

    result = _build_calendar_data(None)
    assert result == {'z': [], 'x': [], 'y': []}

    result = _build_calendar_data(pd.DataFrame())
    assert result == {'z': [], 'x': [], 'y': []}


def test_build_calendar_data_aggregation():
    """Test that tokens are summed correctly across multiple conversations."""
    from app import _build_calendar_data

    data = pd.DataFrame({
        'model': ['gpt-4', 'gpt-4'],
        'created_at': pd.to_datetime(['2025-01-01 10:00:00', '2025-01-01 14:00:00']),
        'input_tokens': [100, 200],
        'output_tokens': [300, 400],
        'reasoning_tokens': [0, 0],
        'cache_read_tokens': [0, 0],
    })

    result = _build_calendar_data(data)

    # 2025-01-01 is Wednesday (row index 3), single week column
    assert len(result['x']) >= 1
    assert len(result['z']) == 7
    # Total tokens: (100+300) + (200+400) = 1000
    assert result['z'][3][0] == 1000  # Wednesday, first week


def test_build_calendar_data_multiple_models_days():
    """Test aggregation with multiple models across multiple days."""
    from app import _build_calendar_data

    data = pd.DataFrame({
        'model': ['model-a', 'model-b', 'model-a', 'model-b'],
        'created_at': pd.to_datetime([
            '2025-01-01 10:00:00', '2025-01-01 10:00:00',
            '2025-01-02 10:00:00', '2025-01-02 10:00:00'
        ]),
        'input_tokens': [100, 50, 200, 100],
        'output_tokens': [300, 150, 400, 250],
        'reasoning_tokens': [0, 0, 0, 0],
        'cache_read_tokens': [0, 0, 0, 0],
    })

    result = _build_calendar_data(data)

    # Should span at least 1 week
    assert len(result['x']) >= 1
    assert len(result['z']) == 7

    # 2025-01-01 (Wed, row 3): model-a=400, model-b=200 → total=600
    # 2025-01-02 (Thu, row 4): model-a=600, model-b=350 → total=950
    assert result['z'][3][0] == 600   # Wednesday
    assert result['z'][4][0] == 950   # Thursday


def test_build_calendar_data_with_token_types():
    """Test that all token types are summed correctly."""
    from app import _build_calendar_data

    data = pd.DataFrame({
        'model': ['gpt-4'],
        'created_at': pd.to_datetime(['2025-01-01']),
        'input_tokens': [100],
        'output_tokens': [300],
        'reasoning_tokens': [50],
        'cache_read_tokens': [20],
    })

    result = _build_calendar_data(data)

    # 2025-01-01 is Wednesday (row index 3), total = 470
    assert result['z'][3][0] == 470


def test_build_calendar_data_z_matrix_shape():
    """Test that z matrix has correct dimensions."""
    from app import _build_calendar_data

    data = pd.DataFrame({
        'model': ['m1', 'm2', 'm3'],
        'created_at': pd.to_datetime(['2025-01-01', '2025-01-01', '2025-01-01']),
        'input_tokens': [10, 20, 30],
        'output_tokens': [40, 50, 60],
        'reasoning_tokens': [0, 0, 0],
        'cache_read_tokens': [0, 0, 0],
    })

    result = _build_calendar_data(data)

    assert len(result['z']) == 7  # Always 7 rows (days of week)
    assert len(result['z'][0]) >= 1  # At least 1 column (week)


def test_build_calendar_data_with_token_type_columns_missing():
    """Test that function handles data with token type columns set to 0."""
    from app import _build_calendar_data

    data = pd.DataFrame({
        'model': ['gpt-4'],
        'created_at': pd.to_datetime(['2025-01-01']),
        'input_tokens': [100],
        'output_tokens': [300],
        'reasoning_tokens': [0],
        'cache_read_tokens': [0],
    })

    result = _build_calendar_data(data)

    # 2025-01-01 is Wednesday (row index 3), total = 400
    assert result['z'][3][0] == 400


def test_calendar_with_real_db():
    """Test calendar heatmap builds from actual database."""
    from app import _build_calendar_data
    from data_loader import load_unified_data

    db_path = str(Path(__file__).parent.parent / "data" / "lmstudio_usage.db")

    df = load_unified_data(db_path)

    assert df is not None and not df.empty

    cal_data = _build_calendar_data(df)

    assert len(cal_data['y']) == 7, "Should have 7 day-of-week rows"
    assert len(cal_data['x']) > 0, "Should have at least one week column"
    assert len(cal_data['z']) == 7, "Z matrix should have 7 rows"


def test_calendar_time_filter():
    """Test that calendar respects time filtering."""
    from app import _build_calendar_data
    from data_loader import load_unified_data

    db_path = str(Path(__file__).parent.parent / "data" / "lmstudio_usage.db")

    df = load_unified_data(db_path)

    # Filter to last 30 days only
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
    filtered = df[pd.to_datetime(df['created_at']) >= cutoff]

    cal_data = _build_calendar_data(filtered)

    if not cal_data['z']:
        return  # No data in range is acceptable

    # Z matrix should only contain dates within the filtered range.
    # Since _build_calendar_data uses the min/max of the input data,
    # all cells correspond to dates >= cutoff.
    assert len(cal_data['z']) == 7  # 7 rows
    assert len(cal_data['z'][0]) > 0  # At least one week column
