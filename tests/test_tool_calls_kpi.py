"""Tests for Total Tool Calls KPI card logic."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_df(tool_calls=None):
    """Helper to create a sample DataFrame with tool_call_count column."""
    if tool_calls is None:
        tool_calls = [100, 200, 300]
    return pd.DataFrame({
        "filename": ["a.json", "b.json", "c.json"],
        "token_count": [1000, 2000, 3000],
        "model": ["gpt-4", "gpt-3.5", "claude"],
        "source": ["lmstudio", "lmstudio", "opencode"],
        "created_at": pd.to_datetime(["2025-06-15", "2025-07-20", "2025-08-10"]),
        "tool_call_count": tool_calls,
    })


def _calc_total_tool_calls(data):
    """Replicate the logic from app.py's total_tool_calls output."""
    if data is None or data.empty:
        return "No data available."
    total = int(data["tool_call_count"].sum())
    return f"{total:,}"


class TestTotalToolCallsCalculation:
    def test_returns_correct_sum(self):
        df = _make_df([100, 200, 300])
        result = _calc_total_tool_calls(df)
        assert result == "600"

    def test_returns_no_data_for_none(self):
        result = _calc_total_tool_calls(None)
        assert result == "No data available."

    def test_returns_no_data_for_empty_df(self):
        empty_df = pd.DataFrame({
            "filename": [],
            "token_count": [],
            "model": [],
            "source": [],
            "created_at": [],
            "tool_call_count": [],
        })
        result = _calc_total_tool_calls(empty_df)
        assert result == "No data available."

    def test_formats_with_commas(self):
        df = _make_df([1234, 5678, 90])
        result = _calc_total_tool_calls(df)
        # 1234 + 5678 + 90 = 7002
        assert result == "7,002"

    def test_large_number_formatting(self):
        df = pd.DataFrame({
            "filename": ["a.json", "b.json"],
            "token_count": [1000, 2000],
            "model": ["gpt-4", "gpt-3.5"],
            "source": ["lmstudio", "lmstudio"],
            "created_at": pd.to_datetime(["2025-06-15", "2025-07-20"]),
            "tool_call_count": [1_000_000, 234_567],
        })
        result = _calc_total_tool_calls(df)
        # 1_000_000 + 234_567 = 1_234_567
        assert result == "1,234,567"

    def test_zero_tool_calls(self):
        df = _make_df([0, 0, 0])
        result = _calc_total_tool_calls(df)
        assert result == "0"

    def test_single_row(self):
        df = pd.DataFrame({
            "filename": ["x.json"],
            "token_count": [500],
            "model": ["gpt-4"],
            "source": ["lmstudio"],
            "created_at": pd.to_datetime(["2025-01-01"]),
            "tool_call_count": [42],
        })
        result = _calc_total_tool_calls(df)
        assert result == "42"

    def test_filtered_data_subset(self):
        df = _make_df([10, 20, 30])
        # Simulate filtering to just 2 rows
        filtered = df.iloc[:2]
        result = _calc_total_tool_calls(filtered)
        assert result == "30"
