"""Tests for calendar heatmap data aggregation."""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Add parent directory to path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_build_calendar_data_basic():
    """Test basic aggregation of tokens per model per day."""
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
    assert 'z' in result  # heatmap values
    assert 'x' in result  # dates
    assert 'y' in result  # models


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


def test_build_calendar_data_sort_by_usage():
    """Test that models are sorted by total usage descending."""
    from app import _build_calendar_data

    data = pd.DataFrame({
        'model': ['small-model', 'big-model', 'small-model'],
        'created_at': pd.to_datetime(['2025-01-01', '2025-01-01', '2025-01-02']),
        'input_tokens': [10, 1000, 20],
        'output_tokens': [10, 2000, 20],
        'reasoning_tokens': [0, 0, 0],
        'cache_read_tokens': [0, 0, 0],
    })

    result = _build_calendar_data(data)

    # big-model should appear before small-model (descending by total usage)
    y_order = result['y']
    assert y_order[0] == 'big-model'


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

    # Should have one date column for 2025-01-01
    assert len(result['x']) == 1
    assert result['x'][0] == '2025-01-01'
    # Should have one model row
    assert result['y'] == ['gpt-4']
    # Total tokens: (100+300) + (200+400) = 1000
    assert result['z'][0][0] == 1000


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

    # Should have two dates
    assert len(result['x']) == 2
    assert set(result['x']) == {'2025-01-01', '2025-01-02'}

    # model-a total: (100+300) + (200+400) = 1000
    # model-b total: (50+150) + (100+250) = 550
    # model-a should be first (higher usage)
    assert result['y'][0] == 'model-a'
    assert result['y'][1] == 'model-b'

    # Verify z matrix values
    # row 0 (model-a): [400, 600] = day1 tokens, day2 tokens
    assert result['z'][0][0] == 400  # model-a on 2025-01-01
    assert result['z'][0][1] == 600  # model-a on 2025-01-02
    assert result['z'][1][0] == 200  # model-b on 2025-01-01
    assert result['z'][1][1] == 350  # model-b on 2025-01-02


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

    # Total: 100 + 300 + 50 + 20 = 470
    assert result['z'][0][0] == 470


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

    assert len(result['z']) == 3  # 3 models
    assert len(result['z'][0]) == 1  # 1 date


def test_build_calendar_data_date_ordering():
    """Test that dates are sorted chronologically."""
    from app import _build_calendar_data

    data = pd.DataFrame({
        'model': ['gpt-4', 'gpt-4', 'gpt-4'],
        'created_at': pd.to_datetime([
            '2025-03-01', '2025-01-01', '2025-02-01'
        ]),
        'input_tokens': [10, 20, 30],
        'output_tokens': [40, 50, 60],
        'reasoning_tokens': [0, 0, 0],
        'cache_read_tokens': [0, 0, 0],
    })

    result = _build_calendar_data(data)

    # Dates should be in chronological order regardless of input order
    assert result['x'] == ['2025-01-01', '2025-02-01', '2025-03-01']


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

    # Should still work, total = 400
    assert result['z'][0][0] == 400
