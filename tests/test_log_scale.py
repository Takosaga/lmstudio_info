"""Tests for log scale on token type chart."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_token_type_chart_has_log_yaxis():
    """When breakdown_by is token_type, the usage chart y-axis should be log scale."""
    app_py = Path(__file__).parent.parent / "app.py"
    source = app_py.read_text()

    assert "yaxis=dict(type='log')" in source, \
        "Token type chart should use log scale on y-axis"


def test_token_type_yaxis_label_indicates_log_scale():
    """The y-axis label for token-type chart should mention 'log'."""
    app_py = Path(__file__).parent.parent / "app.py"
    source = app_py.read_text()

    assert "Total Tokens (log scale)" in source, \
        "Token type y-axis label should indicate log scale"
