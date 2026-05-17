"""Tests for analysis modules."""

from __future__ import annotations

import pandas as pd
import pytest
from MatchMind.analysis.visualisations import (
    plot_shot_map,
    plot_xg_timeline,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_shots_df() -> pd.DataFrame:
    """Sample shot data for visualisation tests."""
    return pd.DataFrame([
        {"location_x": 108.0, "location_y": 34.0, "xg": 0.76, "shot_outcome": "Goal", "team_name": "Argentina", "minute": 23},
        {"location_x": 95.0, "location_y": 50.0, "xg": 0.12, "shot_outcome": "Saved", "team_name": "Argentina", "minute": 35},
        {"location_x": 105.0, "location_y": 40.0, "xg": 0.55, "shot_outcome": "Goal", "team_name": "France", "minute": 80},
        {"location_x": 90.0, "location_y": 60.0, "xg": 0.08, "shot_outcome": "Off T", "team_name": "France", "minute": 67},
    ])


# =============================================================================
# TESTS: Visualisations
# =============================================================================


class TestShotMap:
    """Tests for shot map generation."""

    def test_returns_figure(self, sample_shots_df: pd.DataFrame) -> None:
        """Should return a matplotlib Figure object."""
        from matplotlib.figure import Figure
        fig = plot_shot_map(sample_shots_df, title="Test Shot Map")
        assert isinstance(fig, Figure)

    def test_handles_empty_dataframe(self) -> None:
        """Should not crash on empty data."""
        empty_df = pd.DataFrame(columns=["location_x", "location_y", "xg", "shot_outcome"])
        fig = plot_shot_map(empty_df)
        assert fig is not None


class TestXGTimeline:
    """Tests for interactive xG timeline."""

    def test_returns_plotly_figure(self, sample_shots_df: pd.DataFrame) -> None:
        """Should return a Plotly Figure object."""
        import plotly.graph_objects as go
        fig = plot_xg_timeline(sample_shots_df, "Argentina", "France")
        assert isinstance(fig, go.Figure)

    def test_has_traces_for_both_teams(self, sample_shots_df: pd.DataFrame) -> None:
        """Should contain one trace per team."""
        fig = plot_xg_timeline(sample_shots_df, "Argentina", "France")
        assert len(fig.data) == 2
