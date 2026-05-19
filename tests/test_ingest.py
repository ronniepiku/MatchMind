"""Tests for data ingestion module."""

from __future__ import annotations

import pandas as pd
import pytest

from football_analytics.ingest import (
    _extract_players_from_events,
    normalize_events,
    normalize_lineups,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_raw_events() -> pd.DataFrame:
    """Minimal StatsBomb-like event DataFrame for testing."""
    return pd.DataFrame([
        {
            "id": "abc-123",
            "type": "Shot",
            "team": "Argentina",
            "player": "Lionel Messi",
            "player_id": 5503,
            "period": 1,
            "timestamp": "00:23:15.123",
            "minute": 23,
            "second": 15,
            "possession": 12,
            "possession_team": "Argentina",
            "play_pattern": "From Goal Kick",
            "location": [108.5, 34.2],
            "duration": 1.2,
            "under_pressure": True,
            "shot_statsbomb_xg": 0.45,
            "shot_outcome": "Goal",
        },
        {
            "id": "def-456",
            "type": "Pass",
            "team": "Argentina",
            "player": "Ángel Di María",
            "player_id": 6909,
            "period": 1,
            "timestamp": "00:22:50.000",
            "minute": 22,
            "second": 50,
            "possession": 12,
            "possession_team": "Argentina",
            "play_pattern": "From Goal Kick",
            "location": [75.0, 30.0],
            "duration": 0.8,
            "under_pressure": False,
            "pass_length": 25.3,
            "pass_angle": 0.78,
            "pass_outcome": None,
        },
    ])


@pytest.fixture
def sample_lineups() -> dict[str, pd.DataFrame]:
    """Minimal lineup data."""
    return {
        "Argentina": pd.DataFrame([
            {
                "player_id": 5503,
                "player_name": "Lionel Messi",
                "jersey_number": 10,
                "positions": [{"position": "Right Wing", "from": "0:00:00"}],
            },
            {
                "player_id": 6909,
                "player_name": "Ángel Di María",
                "jersey_number": 11,
                "positions": [{"position": "Left Wing", "from": "0:00:00"}],
            },
        ]),
    }


# =============================================================================
# TESTS: normalize_events
# =============================================================================


class TestNormalizeEvents:
    """Tests for event normalisation logic."""

    def test_extracts_location_coordinates(self, sample_raw_events: pd.DataFrame) -> None:
        """Location list [x, y] should be split into separate columns."""
        result = normalize_events(sample_raw_events, match_id=12345)
        assert result["location_x"].iloc[0] == pytest.approx(108.5)
        assert result["location_y"].iloc[0] == pytest.approx(34.2)

    def test_extracts_xg(self, sample_raw_events: pd.DataFrame) -> None:
        """xG should be extracted from shot_statsbomb_xg column."""
        result = normalize_events(sample_raw_events, match_id=12345)
        shot_row = result[result["event_type"] == "Shot"].iloc[0]
        assert shot_row["xg"] == pytest.approx(0.45)

    def test_sets_match_id(self, sample_raw_events: pd.DataFrame) -> None:
        """match_id should be assigned to all rows."""
        result = normalize_events(sample_raw_events, match_id=99999)
        assert (result["match_id"] == 99999).all()

    def test_handles_missing_location(self) -> None:
        """Events without location should get None coordinates."""
        df = pd.DataFrame([{
            "id": "xxx-999",
            "type": "Half Start",
            "team": "Argentina",
            "period": 1,
            "timestamp": "00:00:00",
            "minute": 0,
            "second": 0,
        }])
        result = normalize_events(df, match_id=1)
        assert pd.isna(result["location_x"].iloc[0])

    def test_boolean_defaults(self, sample_raw_events: pd.DataFrame) -> None:
        """Boolean fields should default to False when missing."""
        result = normalize_events(sample_raw_events, match_id=1)
        assert result["counterpress"].dtype == bool
        assert not result["counterpress"].iloc[0]



# =============================================================================
# TESTS: _extract_players_from_events
# =============================================================================


class TestExtractPlayers:
    """Tests for player extraction from event data."""

    def test_extracts_unique_players(self, sample_raw_events: pd.DataFrame) -> None:
        """Should return deduplicated player list."""
        result = _extract_players_from_events(sample_raw_events)
        assert len(result) == 2
        assert set(result["player_id"]) == {5503, 6909}

    def test_handles_missing_player_column(self) -> None:
        """Should return empty DataFrame when player_id column is missing."""
        df = pd.DataFrame([{"id": "x", "type": "Half Start"}])
        result = _extract_players_from_events(df)
        assert result.empty
