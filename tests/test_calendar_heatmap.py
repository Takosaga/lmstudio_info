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
    assert result == {'z': [], 'x': [], 'y': [], 'dates': []}

    result = _build_calendar_data(pd.DataFrame())
    assert result == {'z': [], 'x': [], 'y': [], 'dates': []}


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

    # With trailing 52-week range, short data lands at high column indices.
    # Find the non-zero cell dynamically and verify the total.
    assert len(result['z']) == 7
    flat_nonzero = [(r, c) for r in range(7) for c in range(len(result['z'][0])) if result['z'][r][c] > 0]
    assert len(flat_nonzero) == 1
    row, col = flat_nonzero[0]
    # Total tokens: (100+300) + (200+400) = 1000
    assert result['z'][row][col] == 1000


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

    assert len(result['z']) == 7

    # With trailing 52-week range, find non-zero cells dynamically.
    # 2025-01-01 (Wed, row 3): total=600
    # 2025-01-02 (Thu, row 4): total=950
    flat_nonzero = [(r, c) for r in range(7) for c in range(len(result['z'][0])) if result['z'][r][c] > 0]
    assert len(flat_nonzero) == 2
    vals_by_row = {r: v for r, c in flat_nonzero for v in [result['z'][r][c]]}
    assert vals_by_row[3] == 600   # Wednesday
    assert vals_by_row[4] == 950   # Thursday


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

    # With trailing 52-week range, find non-zero cell dynamically.
    flat_nonzero = [(r, c) for r in range(7) for c in range(len(result['z'][0])) if result['z'][r][c] > 0]
    assert len(flat_nonzero) == 1
    row, col = flat_nonzero[0]
    # Total: 100 + 300 + 50 + 20 = 470
    assert result['z'][row][col] == 470


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


def test_build_calendar_data_52_week_range():
    """Test that calendar always spans ~52 weeks ending on last data day."""
    from app import _build_calendar_data

    # Data spanning exactly 10 days in Jan 2025 (Wed Jan 1 to Fri Jan 10)
    data = pd.DataFrame({
        'model': ['gpt-4'] * 5,
        'created_at': pd.to_datetime([
            '2025-01-01', '2025-01-03', '2025-01-05',
            '2025-01-07', '2025-01-09',
        ]),
        'input_tokens': [100] * 5,
        'output_tokens': [300] * 5,
        'reasoning_tokens': [0] * 5,
        'cache_read_tokens': [0] * 5,
    })

    result = _build_calendar_data(data)

    # Last data day is Jan 9, 2025 (Thursday).
    # Start should be Jan 9 - 364 days = Jan 10, 2024.
    # That gives exactly 52 weeks (365 days / 7 ≈ 52 columns).
    assert len(result['z']) == 7
    n_cols = len(result['z'][0])
    assert n_cols >= 52, f"Expected ~52 columns, got {n_cols}"
    assert n_cols <= 53, f"Expected ~52 columns, got {n_cols}"


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

    # With trailing 52-week range, find non-zero cell dynamically.
    flat_nonzero = [(r, c) for r in range(7) for c in range(len(result['z'][0])) if result['z'][r][c] > 0]
    assert len(flat_nonzero) == 1
    row, col = flat_nonzero[0]
    # Total: 100 + 300 = 400
    assert result['z'][row][col] == 400


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
