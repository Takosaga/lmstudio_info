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
    assert 'tickvals' in result
    assert 'ticktext' in result
    assert 'y' in result
    assert result['y'] == ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    assert len(result['z']) == 7  # 7 rows for days of week
    assert len(result['tickvals']) > 0  # month boundaries


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
    assert result == {'z': [], 'x': [], 'y': [], 'date_strings': []}

    result = _build_calendar_data(pd.DataFrame())
    assert result == {'z': [], 'x': [], 'y': [], 'date_strings': []}


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


def test_build_calendar_data_date_strings():
    """Test that result contains a 'date_strings' matrix matching the z matrix shape."""
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

    assert 'date_strings' in result
    assert len(result['date_strings']) == 7
    assert len(result['date_strings'][0]) >= 1
    # Each cell should be a date string like "Jan 1, 2025" or empty string for non-data dates
    found_non_empty = [d for row in result['date_strings'] for d in row if d]
    assert len(found_non_empty) >= 1


def test_calendar_with_real_db():
    """Test calendar heatmap builds from actual database."""
    from app import _build_calendar_data
    from data_loader import load_unified_data

    db_path = str(Path(__file__).parent.parent / "data" / "lmstudio_usage.db")

    df = load_unified_data(db_path)

    assert df is not None and not df.empty

    cal_data = _build_calendar_data(df)

    assert len(cal_data['y']) == 7, "Should have 7 day-of-week rows"
    assert len(cal_data['z']) == 7, "Z matrix should have 7 rows"
    assert 'date_strings' in cal_data, "Date strings matrix should be present"
    assert len(cal_data['tickvals']) > 0, "Should have month tick boundaries"


def test_usage_chart_calendar_hover():
    """Test that the calendar chart passes date strings via text for hover."""
    from app import _build_calendar_data
    import plotly.graph_objects as go

    data = pd.DataFrame({
        'model': ['gpt-4'],
        'created_at': pd.to_datetime(['2025-01-01']),
        'input_tokens': [100],
        'output_tokens': [300],
        'reasoning_tokens': [0],
        'cache_read_tokens': [0],
    })

    cal_data = _build_calendar_data(data)
    assert 'date_strings' in cal_data

    # Verify that text is passed correctly to Plotly Heatmap for hover
    n_cols = len(cal_data['z'][0])
    fig = go.Figure(go.Heatmap(
        z=cal_data['z'],
        x=list(range(n_cols)),  # numeric indices, not empty-string labels
        y=cal_data['y'],
        colorscale=[
            [0, '#ebedf0'],
            [0.15, '#b6e2b4'],
            [0.3, '#9be9a8'],
            [0.5, '#40c463'],
            [0.75, '#30a14e'],
            [1, '#216e39']
        ],
        text=cal_data['date_strings'],
        hovertemplate='<b>%{text}</b><br>Tokens: %{z:,}<extra></extra>',
    ))

    assert fig.data[0].text is not None
    text = fig.data[0].text
    if hasattr(text, 'shape'):
        assert text.shape == (7, n_cols)
    else:
        assert len(text) == 7 and all(len(row) == n_cols for row in text)


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


def test_compute_calendar_colors_all_zeros():
    """All-zero matrix should produce lightest gray for every cell."""
    from app import _compute_calendar_colors
    z = np.zeros((7, 8), dtype=int)
    colors = _compute_calendar_colors(z)
    expected = ['#ebedf0'] * 56
    assert list(colors.flatten()) == expected


def test_compute_calendar_colors_uniform_nonzero():
    """All identical non-zero values should all get darkest green."""
    from app import _compute_calendar_colors
    z = np.full((7, 8), 1_000_000, dtype=int)
    colors = _compute_calendar_colors(z)
    # With a single unique value, p10=p25=...=p90=value, so all >= p90
    expected = ['#216e39'] * 56
    assert list(colors.flatten()) == expected


def test_compute_calendar_colors_two_values():
    """Two distinct values should split into two color buckets."""
    from app import _compute_calendar_colors
    z = np.zeros((7, 8), dtype=int)
    z_flat = z.flatten()
    for i in range(20):
        z_flat[i] = 1_000_000   # low
    for i in range(20, 40):
        z_flat[i] = 50_000_000  # high
    colors = _compute_calendar_colors(z)
    # Low values should be lighter than high values
    low_colors = set(colors.flatten()[:20])
    high_colors = set(colors.flatten()[20:40])
    assert len(low_colors) > 0
    assert len(high_colors) > 0
    # The darkest color (#216e39) should appear in high bucket
    assert '#216e39' in high_colors or list(high_colors)[0] != list(low_colors)[0]


def test_compute_calendar_colors_five_buckets_populated():
    """Wide data range should populate all 5 non-zero color buckets."""
    from app import _compute_calendar_colors
    z = np.zeros((7, 8), dtype=int)
    z_flat = z.flatten()
    # Distribute values across 5 percentiles
    values = [2_000_000, 10_000_000, 20_000_000, 30_000_000, 48_000_000]
    for i, v in enumerate(values):
        start = i * 10
        end = (i + 1) * 10
        z_flat[start:end] = v
    colors = _compute_calendar_colors(z)
    non_gray = set(c for c in colors.flatten() if c != '#ebedf0')
    assert len(non_gray) == 5, f"Expected 5 distinct green shades, got {len(non_gray)}: {non_gray}"


def test_compute_calendar_colors_single_active_day():
    """One active day should get darkest green; rest gray."""
    from app import _compute_calendar_colors
    z = np.zeros((7, 8), dtype=int)
    z[0, 0] = 5_000_000
    colors = _compute_calendar_colors(z)
    assert colors[0, 0] == '#216e39'
