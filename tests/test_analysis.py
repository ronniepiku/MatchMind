"""Tests for analysis modules."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from football_analytics.analysis.visualisations import (
    plot_shot_map,
    plot_xg_timeline,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_shots_df() -> pd.DataFrame:
    """Sample shot data for visualisation tests."""
    return pd.DataFrame(
        [
            {
                "location_x": 108.0,
                "location_y": 34.0,
                "xg": 0.76,
                "shot_outcome": "Goal",
                "team_name": "Argentina",
                "minute": 23,
            },
            {
                "location_x": 95.0,
                "location_y": 50.0,
                "xg": 0.12,
                "shot_outcome": "Saved",
                "team_name": "Argentina",
                "minute": 35,
            },
            {
                "location_x": 105.0,
                "location_y": 40.0,
                "xg": 0.55,
                "shot_outcome": "Goal",
                "team_name": "France",
                "minute": 80,
            },
            {
                "location_x": 90.0,
                "location_y": 60.0,
                "xg": 0.08,
                "shot_outcome": "Off T",
                "team_name": "France",
                "minute": 67,
            },
        ]
    )


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


# =============================================================================
# TESTS: xG Model
# =============================================================================


class TestXGModel:
    """Tests for the custom xG model."""

    @pytest.fixture
    def sample_shots(self) -> pd.DataFrame:
        """Sample shot data with known characteristics."""
        return pd.DataFrame(
            [
                {
                    "location_x": 112.0,
                    "location_y": 40.0,
                    "shot_outcome": "Goal",
                    "shot_body_part": "Right Foot",
                    "under_pressure": False,
                    "play_pattern": "Regular Play",
                    "minute": 23,
                },
                {
                    "location_x": 95.0,
                    "location_y": 60.0,
                    "shot_outcome": "Saved",
                    "shot_body_part": "Head",
                    "under_pressure": True,
                    "play_pattern": "Regular Play",
                    "minute": 35,
                },
                {
                    "location_x": 108.0,
                    "location_y": 38.0,
                    "shot_outcome": "Goal",
                    "shot_body_part": "Left Foot",
                    "under_pressure": False,
                    "play_pattern": "Regular Play",
                    "minute": 67,
                },
                {
                    "location_x": 85.0,
                    "location_y": 45.0,
                    "shot_outcome": "Off T",
                    "shot_body_part": "Right Foot",
                    "under_pressure": False,
                    "play_pattern": "Regular Play",
                    "minute": 12,
                },
                {
                    "location_x": 115.0,
                    "location_y": 40.0,
                    "shot_outcome": "Goal",
                    "shot_body_part": "Right Foot",
                    "under_pressure": False,
                    "play_pattern": "From Penalty",
                    "minute": 75,
                },
                {
                    "location_x": 100.0,
                    "location_y": 30.0,
                    "shot_outcome": "Blocked",
                    "shot_body_part": "Right Foot",
                    "under_pressure": True,
                    "play_pattern": "Regular Play",
                    "minute": 50,
                },
            ]
            * 20
        )  # Multiply for enough training data

    def test_engineer_features_creates_expected_columns(self, sample_shots: pd.DataFrame) -> None:
        """Feature engineering should create all expected columns."""
        from football_analytics.analysis.xg_model import engineer_features

        result = engineer_features(sample_shots)
        expected_cols = [
            "distance_to_goal",
            "goal_angle",
            "is_header",
            "under_pressure_flag",
            "is_penalty",
            "in_box",
            "central",
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_distance_to_goal_correct(self, sample_shots: pd.DataFrame) -> None:
        """Distance calculation should be geometrically correct."""
        from football_analytics.analysis.xg_model import engineer_features

        result = engineer_features(sample_shots)
        # First shot is at (112, 40) — distance to goal (120, 40) = 8.0
        assert result["distance_to_goal"].iloc[0] == pytest.approx(8.0, abs=0.01)

    def test_penalty_detection(self, sample_shots: pd.DataFrame) -> None:
        """Penalties should be correctly identified."""
        from football_analytics.analysis.xg_model import engineer_features

        result = engineer_features(sample_shots)
        # 5th shot (index 4) is "From Penalty"
        assert result["is_penalty"].iloc[4] == 1

    def test_train_model_returns_pipeline(self, sample_shots: pd.DataFrame) -> None:
        """Training should return a fitted Pipeline."""
        from football_analytics.analysis.xg_model import train_xg_model

        model, metrics, cv_probs = train_xg_model(sample_shots, cv_folds=3)
        assert hasattr(model, "predict_proba")
        assert metrics.n_shots == len(sample_shots)
        assert 0 <= metrics.roc_auc <= 1
        assert len(cv_probs) == len(sample_shots)

    def test_predictions_in_valid_range(self, sample_shots: pd.DataFrame) -> None:
        """All xG predictions should be between 0 and 1."""
        from football_analytics.analysis.xg_model import predict_xg, train_xg_model

        model, _, _ = train_xg_model(sample_shots, cv_folds=3)
        predictions = predict_xg(model, sample_shots)
        assert np.all(predictions >= 0)
        assert np.all(predictions <= 1)


# =============================================================================
# TESTS: Advanced xG Model
# =============================================================================


class TestAdvancedXG:
    """Tests for gradient boosting xG model."""

    @pytest.fixture
    def shot_data(self) -> pd.DataFrame:
        """Generate synthetic shot data for testing."""
        rng = np.random.default_rng(42)
        n = 200

        locations_x = rng.uniform(85, 120, n)
        locations_y = rng.uniform(15, 65, n)
        distances = np.sqrt((locations_x - 120) ** 2 + (locations_y - 40) ** 2)

        # Higher probability of goal for closer shots
        goal_prob = 1 / (1 + np.exp(0.15 * distances - 2))
        goals = rng.binomial(1, goal_prob)

        return pd.DataFrame(
            {
                "location_x": locations_x,
                "location_y": locations_y,
                "shot_body_part": rng.choice(["Foot", "Head"], n, p=[0.75, 0.25]),
                "under_pressure": rng.choice([True, False], n, p=[0.3, 0.7]),
                "play_pattern": "From Open Play",
                "shot_type": rng.choice(["Open Play", "Penalty", "Free Kick"], n, p=[0.88, 0.07, 0.05]),
                "shot_outcome": np.where(goals, "Goal", "Off T"),
                "minute": rng.integers(1, 90, n),
            }
        )

    def test_advanced_feature_engineering(self, shot_data: pd.DataFrame) -> None:
        from football_analytics.analysis.xg_model_advanced import (
            engineer_advanced_features,
            get_advanced_feature_columns,
        )

        df = engineer_advanced_features(shot_data)
        cols = get_advanced_feature_columns()
        for col in cols:
            assert col in df.columns, f"Missing feature: {col}"

    def test_train_advanced_model(self, shot_data: pd.DataFrame) -> None:
        from football_analytics.analysis.xg_model_advanced import (
            train_advanced_xg_model,
        )

        result = train_advanced_xg_model(shot_data, backend="hist", tune_hyperparams=False, calibrate=False)
        assert result.metrics.roc_auc > 0.55  # Better than random
        assert 0 <= result.metrics.brier_score <= 0.25
        assert len(result.cv_predictions) == len(shot_data)

    def test_predict_advanced(self, shot_data: pd.DataFrame) -> None:
        from football_analytics.analysis.xg_model_advanced import (
            predict_advanced_xg,
            train_advanced_xg_model,
        )

        result = train_advanced_xg_model(shot_data, backend="hist", tune_hyperparams=False, calibrate=False)
        preds = predict_advanced_xg(result.model, shot_data.head(10))
        assert len(preds) == 10
        assert all(0 <= p <= 1 for p in preds)

    def test_feature_importance(self, shot_data: pd.DataFrame) -> None:
        from football_analytics.analysis.xg_model_advanced import (
            train_advanced_xg_model,
        )

        result = train_advanced_xg_model(shot_data, backend="hist", tune_hyperparams=False, calibrate=False)
        assert not result.feature_importance.empty
        assert "feature" in result.feature_importance.columns
        assert "importance" in result.feature_importance.columns


# =============================================================================
# TESTS: Player Similarity
# =============================================================================


class TestPlayerSimilarity:
    """Tests for the player similarity engine."""

    @pytest.fixture
    def player_vectors(self) -> pd.DataFrame:
        """Sample player feature vectors."""
        np.random.seed(42)
        n = 20
        return pd.DataFrame(
            {
                "player_id": range(1, n + 1),
                "player_name": [f"Player_{i}" for i in range(1, n + 1)],
                "team_id": [1] * 10 + [2] * 10,
                "team_name": ["Team A"] * 10 + ["Team B"] * 10,
                "appearances": np.random.randint(5, 20, n),
                "xg_per_match": np.random.uniform(0, 0.8, n),
                "xa_per_match": np.random.uniform(0, 0.5, n),
                "passes_per_match": np.random.uniform(20, 60, n),
                "pass_accuracy": np.random.uniform(0.6, 0.95, n),
                "dribbles_per_match": np.random.uniform(0, 4, n),
                "pressures_per_match": np.random.uniform(5, 25, n),
                "tackles_per_match": np.random.uniform(0, 5, n),
            }
        )

    def test_find_similar_returns_correct_count(self, player_vectors: pd.DataFrame) -> None:
        """Should return the requested number of similar players."""
        from football_analytics.analysis.similarity import find_similar_players

        result = find_similar_players(1, player_vectors, top_n=5)
        assert len(result) == 5

    def test_similarity_scores_valid_range(self, player_vectors: pd.DataFrame) -> None:
        """Similarity scores should be between -1 and 1."""
        from football_analytics.analysis.similarity import find_similar_players

        result = find_similar_players(1, player_vectors, top_n=10)
        assert result["similarity"].min() >= -1
        assert result["similarity"].max() <= 1

    def test_target_not_in_results(self, player_vectors: pd.DataFrame) -> None:
        """The target player should not appear in their own similarity results."""
        from football_analytics.analysis.similarity import find_similar_players

        result = find_similar_players(1, player_vectors, top_n=19)
        assert 1 not in result["player_id"].values

    def test_raises_on_missing_player(self, player_vectors: pd.DataFrame) -> None:
        """Should raise ValueError for non-existent player."""
        from football_analytics.analysis.similarity import find_similar_players

        with pytest.raises(ValueError):
            find_similar_players(999, player_vectors)


# =============================================================================
# TESTS: Tracking Data
# =============================================================================


class TestTrackingData:
    """Tests for tracking data integration."""

    def test_coordinate_conversion_roundtrip(self) -> None:
        """Converting SB → tracking → SB should return original values."""
        from football_analytics.analysis.tracking import (
            convert_coordinates_sb_to_tracking,
            convert_coordinates_tracking_to_sb,
        )

        x_sb, y_sb = 60.0, 40.0
        x_t, y_t = convert_coordinates_sb_to_tracking(x_sb, y_sb)
        x_back, y_back = convert_coordinates_tracking_to_sb(x_t, y_t)
        assert x_back == pytest.approx(x_sb, abs=0.01)
        assert y_back == pytest.approx(y_sb, abs=0.01)

    def test_pitch_control_output_shape(self) -> None:
        """Pitch control should return correct grid dimensions."""
        from football_analytics.analysis.tracking import calculate_pitch_control

        home = np.array([[50, 34], [60, 30], [40, 40]])
        away = np.array([[55, 35], [45, 25], [70, 50]])
        ball = np.array([52, 34])

        control = calculate_pitch_control(ball, home, away, grid_resolution=5.0)
        assert control.shape == (14, 21)  # 68/5=13.6→14, 105/5=21

    def test_pitch_control_values_bounded(self) -> None:
        """Pitch control values should be in [-1, 1]."""
        from football_analytics.analysis.tracking import calculate_pitch_control

        home = np.array([[50, 34], [30, 20]])
        away = np.array([[80, 50], [90, 34]])
        ball = np.array([50, 34])

        control = calculate_pitch_control(ball, home, away, grid_resolution=10.0)
        assert np.all(control >= -1)
        assert np.all(control <= 1)

    def test_physical_metrics(self) -> None:
        """Physical metrics should produce expected values for known data."""
        from football_analytics.analysis.tracking import calculate_physical_metrics

        # Player moves 1m/frame at 25fps = 25 m/s (very fast, but for testing)
        tracking = pd.DataFrame(
            {
                "timestamp": np.arange(0, 4, 0.04),  # 100 frames at 25fps
                "x": np.linspace(0, 50, 100),
                "y": np.zeros(100),
            }
        )

        metrics = calculate_physical_metrics(tracking, fps=25)
        assert metrics["total_distance_m"] == pytest.approx(50.0, abs=1.0)
        assert metrics["max_speed_ms"] > 0

    def test_team_shape_metrics(self) -> None:
        """Team shape calculation should return valid metrics."""
        from football_analytics.analysis.tracking import calculate_team_shape

        positions = np.array(
            [
                [20, 30],
                [20, 38],
                [22, 34],
                [21, 42],  # Back 4
                [40, 25],
                [38, 34],
                [42, 45],  # Midfield
                [55, 20],
                [60, 40],
                [58, 55],  # Attack
            ]
        )

        shape = calculate_team_shape(positions)
        assert shape["width"] > 0
        assert shape["length"] > 0
        assert shape["defensive_line_height"] == pytest.approx(np.mean([20, 20, 21, 22]), abs=0.1)


# =============================================================================
# TESTS: Possession Chains
# =============================================================================


class TestPossessionChains:
    """Tests for possession chain extraction and analysis."""

    @pytest.fixture
    def sample_events(self) -> pd.DataFrame:
        """Create sample event data for two possessions."""
        return pd.DataFrame(
            [
                # Possession 1: short build-up ending in shot
                {
                    "match_id": 1,
                    "possession": 1,
                    "team_id": 10,
                    "player_id": 101,
                    "event_type": "Pass",
                    "minute": 5,
                    "second": 10,
                    "location_x": 35.0,
                    "location_y": 40.0,
                    "end_location_x": 50.0,
                    "end_location_y": 45.0,
                    "pass_outcome": None,
                    "pass_length": 16.0,
                    "play_pattern": "From Open Play",
                    "xg": None,
                    "shot_outcome": None,
                    "key_pass": False,
                },
                {
                    "match_id": 1,
                    "possession": 1,
                    "team_id": 10,
                    "player_id": 102,
                    "event_type": "Pass",
                    "minute": 5,
                    "second": 15,
                    "location_x": 50.0,
                    "location_y": 45.0,
                    "end_location_x": 70.0,
                    "end_location_y": 40.0,
                    "pass_outcome": None,
                    "pass_length": 21.0,
                    "play_pattern": "From Open Play",
                    "xg": None,
                    "shot_outcome": None,
                    "key_pass": False,
                },
                {
                    "match_id": 1,
                    "possession": 1,
                    "team_id": 10,
                    "player_id": 103,
                    "event_type": "Pass",
                    "minute": 5,
                    "second": 20,
                    "location_x": 70.0,
                    "location_y": 40.0,
                    "end_location_x": 95.0,
                    "end_location_y": 38.0,
                    "pass_outcome": None,
                    "pass_length": 25.0,
                    "play_pattern": "From Open Play",
                    "xg": None,
                    "shot_outcome": None,
                    "key_pass": True,
                },
                {
                    "match_id": 1,
                    "possession": 1,
                    "team_id": 10,
                    "player_id": 104,
                    "event_type": "Shot",
                    "minute": 5,
                    "second": 23,
                    "location_x": 95.0,
                    "location_y": 38.0,
                    "end_location_x": 120.0,
                    "end_location_y": 40.0,
                    "pass_outcome": None,
                    "pass_length": None,
                    "play_pattern": "From Open Play",
                    "xg": 0.15,
                    "shot_outcome": "Saved",
                    "key_pass": False,
                },
                # Possession 2: counter attack ending in goal
                {
                    "match_id": 1,
                    "possession": 2,
                    "team_id": 10,
                    "player_id": 101,
                    "event_type": "Pass",
                    "minute": 10,
                    "second": 5,
                    "location_x": 25.0,
                    "location_y": 50.0,
                    "end_location_x": 80.0,
                    "end_location_y": 35.0,
                    "pass_outcome": None,
                    "pass_length": 57.0,
                    "play_pattern": "From Open Play",
                    "xg": None,
                    "shot_outcome": None,
                    "key_pass": False,
                },
                {
                    "match_id": 1,
                    "possession": 2,
                    "team_id": 10,
                    "player_id": 105,
                    "event_type": "Shot",
                    "minute": 10,
                    "second": 10,
                    "location_x": 105.0,
                    "location_y": 40.0,
                    "end_location_x": 120.0,
                    "end_location_y": 40.0,
                    "pass_outcome": None,
                    "pass_length": None,
                    "play_pattern": "From Open Play",
                    "xg": 0.35,
                    "shot_outcome": "Goal",
                    "key_pass": False,
                },
            ]
        )

    def test_extract_chains(self, sample_events: pd.DataFrame) -> None:
        from football_analytics.analysis.possession_chains import (
            extract_possession_chains,
        )

        chains = extract_possession_chains(sample_events)
        assert len(chains) == 2

    def test_chain_outcome_classification(self, sample_events: pd.DataFrame) -> None:
        from football_analytics.analysis.possession_chains import (
            ChainOutcome,
            extract_possession_chains,
        )

        chains = extract_possession_chains(sample_events)
        assert chains[0].outcome == ChainOutcome.SHOT_ON_TARGET
        assert chains[1].outcome == ChainOutcome.GOAL

    def test_chain_xg(self, sample_events: pd.DataFrame) -> None:
        from football_analytics.analysis.possession_chains import (
            extract_possession_chains,
        )

        chains = extract_possession_chains(sample_events)
        assert chains[0].xg_generated == pytest.approx(0.15, abs=0.01)
        assert chains[1].xg_generated == pytest.approx(0.35, abs=0.01)

    def test_chain_style_classification(self, sample_events: pd.DataFrame) -> None:
        from football_analytics.analysis.possession_chains import (
            BuildUpStyle,
            extract_possession_chains,
        )

        chains = extract_possession_chains(sample_events)
        # Second chain: fast transition (< 10s, > 40m progress)
        assert chains[1].style == BuildUpStyle.COUNTER_ATTACK

    def test_chains_to_dataframe(self, sample_events: pd.DataFrame) -> None:
        from football_analytics.analysis.possession_chains import (
            chains_to_dataframe,
            extract_possession_chains,
        )

        chains = extract_possession_chains(sample_events)
        df = chains_to_dataframe(chains)
        assert len(df) == 2
        assert "outcome" in df.columns
        assert "style" in df.columns

    def test_team_possession_profile(self, sample_events: pd.DataFrame) -> None:
        from football_analytics.analysis.possession_chains import (
            chains_to_dataframe,
            compute_team_possession_profile,
            extract_possession_chains,
        )

        chains = extract_possession_chains(sample_events)
        df = chains_to_dataframe(chains)
        profile = compute_team_possession_profile(df, team_id=10)
        assert profile["total_chains"] == 2
        assert profile["dangerous_possession_rate"] > 0


# =============================================================================
# TESTS: Set Pieces
# =============================================================================


class TestSetPieces:
    """Tests for set-piece extraction and analysis."""

    @pytest.fixture
    def corner_events(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "match_id": 1,
                    "possession": 5,
                    "team_id": 10,
                    "player_id": 101,
                    "event_type": "Pass",
                    "minute": 30,
                    "second": 0,
                    "location_x": 120.0,
                    "location_y": 0.0,
                    "end_location_x": 115.0,
                    "end_location_y": 38.0,
                    "pass_outcome": None,
                    "pass_type": "Inswinging",
                    "play_pattern": "From Corner",
                    "xg": None,
                    "shot_outcome": None,
                    "player_name": "Corner Taker",
                },
                {
                    "match_id": 1,
                    "possession": 5,
                    "team_id": 10,
                    "player_id": 102,
                    "event_type": "Shot",
                    "minute": 30,
                    "second": 3,
                    "location_x": 113.0,
                    "location_y": 39.0,
                    "end_location_x": 120.0,
                    "end_location_y": 40.0,
                    "pass_outcome": None,
                    "pass_type": None,
                    "play_pattern": "From Corner",
                    "xg": 0.08,
                    "shot_outcome": "Goal",
                    "player_name": "Header Scorer",
                },
            ]
        )

    def test_extract_set_pieces(self, corner_events: pd.DataFrame) -> None:
        from football_analytics.analysis.set_pieces import extract_set_pieces

        sequences = extract_set_pieces(corner_events)
        assert len(sequences) == 1
        assert sequences[0].set_piece_type.value == "corner"

    def test_corner_outcome(self, corner_events: pd.DataFrame) -> None:
        from football_analytics.analysis.set_pieces import extract_set_pieces

        sequences = extract_set_pieces(corner_events)
        assert sequences[0].outcome == "goal"
        assert sequences[0].xg_generated == pytest.approx(0.08, abs=0.01)

    def test_set_piece_efficiency(self, corner_events: pd.DataFrame) -> None:
        from football_analytics.analysis.set_pieces import (
            compute_set_piece_efficiency,
            extract_set_pieces,
            set_pieces_to_dataframe,
        )

        sequences = extract_set_pieces(corner_events)
        df = set_pieces_to_dataframe(sequences)
        efficiency = compute_set_piece_efficiency(df, team_id=10)
        assert efficiency["corner_goal_rate"] == 1.0


# =============================================================================
# TESTS: Player Development
# =============================================================================


class TestPlayerDevelopment:
    """Tests for player development tracking."""

    @pytest.fixture
    def per90_data(self) -> pd.DataFrame:
        """Create multi-season per-90 data for a developing player."""
        return pd.DataFrame(
            [
                {
                    "player_id": 1,
                    "season_id": 1,
                    "matches": 20,
                    "minutes_played": 1400,
                    "goals_per_90": 0.10,
                    "xg_per_90": 0.15,
                    "shots_per_90": 2.0,
                    "xa_per_90": 0.05,
                    "successful_dribbles_per_90": 1.0,
                    "pressures_per_90": 8.0,
                },
                {
                    "player_id": 1,
                    "season_id": 2,
                    "matches": 30,
                    "minutes_played": 2200,
                    "goals_per_90": 0.20,
                    "xg_per_90": 0.25,
                    "shots_per_90": 2.8,
                    "xa_per_90": 0.08,
                    "successful_dribbles_per_90": 1.3,
                    "pressures_per_90": 9.0,
                },
                {
                    "player_id": 1,
                    "season_id": 3,
                    "matches": 35,
                    "minutes_played": 2800,
                    "goals_per_90": 0.35,
                    "xg_per_90": 0.38,
                    "shots_per_90": 3.5,
                    "xa_per_90": 0.12,
                    "successful_dribbles_per_90": 1.8,
                    "pressures_per_90": 10.0,
                },
            ]
        )

    def test_development_profile(self, per90_data: pd.DataFrame) -> None:
        from football_analytics.analysis.development import compute_development_profile

        profile = compute_development_profile(
            per90_data, player_id=1, position_group="forward", player_name="Test Player"
        )
        assert profile.trajectory in ("improving", "breakout")
        assert profile.player_name == "Test Player"

    def test_trend_slopes_positive(self, per90_data: pd.DataFrame) -> None:
        from football_analytics.analysis.development import compute_development_profile

        profile = compute_development_profile(per90_data, player_id=1, position_group="forward")
        # All metrics are improving
        for slope in profile.trend_slopes.values():
            assert slope > 0

    def test_generate_report(self, per90_data: pd.DataFrame) -> None:
        from football_analytics.analysis.development import (
            compute_development_profile,
            generate_development_report,
        )

        profile = compute_development_profile(per90_data, player_id=1, position_group="forward")
        report = generate_development_report(profile)
        assert "Development Report" in report
        assert "↑" in report  # Upward trend indicators


# =============================================================================
# TESTS: Spatial Dominance
# =============================================================================


class TestSpatialDominance:
    """Tests for Voronoi tessellation and spatial analysis."""

    def test_voronoi_frame_basic(self) -> None:
        from football_analytics.analysis.spatial import compute_voronoi_frame

        home = np.array([[20.0, 34.0], [40.0, 20.0], [40.0, 48.0], [60.0, 34.0], [70.0, 34.0]])
        away = np.array([[80.0, 34.0], [60.0, 20.0], [60.0, 48.0], [50.0, 34.0], [45.0, 34.0]])

        frame = compute_voronoi_frame(home, away)
        # Total controlled area should approximate pitch area
        total = frame.home_control_area + frame.away_control_area
        assert total > 0  # Some area computed

    def test_defensive_coverage(self) -> None:
        from football_analytics.analysis.spatial import compute_defensive_coverage

        defenders = np.array([[20.0, 30.0], [25.0, 45.0], [30.0, 20.0], [30.0, 55.0]])
        coverage = compute_defensive_coverage(defenders)
        assert coverage.shape[0] > 0
        assert coverage.shape[1] > 0
        # Minimum distance should be 0 (at defender location)
        assert coverage.min() >= 0

    def test_passing_lanes(self) -> None:
        from football_analytics.analysis.spatial import compute_passing_lanes

        teammates = np.array([[50.0, 30.0], [60.0, 40.0], [70.0, 50.0]])
        opponents = np.array([[55.0, 35.0], [65.0, 45.0]])
        ball = np.array([40.0, 35.0])

        lanes = compute_passing_lanes(teammates, opponents, ball)
        assert len(lanes) == 3
        assert "is_open" in lanes.columns
        assert "lane_quality" in lanes.columns

    def test_team_compactness(self) -> None:
        from football_analytics.analysis.spatial import compute_team_compactness

        # Compact team
        compact = np.array(
            [
                [40.0, 30.0],
                [42.0, 32.0],
                [38.0, 34.0],
                [41.0, 36.0],
                [43.0, 28.0],
                [5.0, 34.0],  # GK
            ]
        )
        result = compute_team_compactness(compact, exclude_gk=True)
        assert result["compactness_area"] > 0
        assert result["team_length"] < 10  # Very compact

    def test_space_creation_events(self) -> None:
        from football_analytics.analysis.spatial import identify_space_creation_events

        events = pd.DataFrame(
            [
                {
                    "team_id": 10,
                    "event_type": "Carry",
                    "location_x": 40.0,
                    "carry_end_x": 60.0,
                    "match_id": 1,
                    "minute": 10,
                    "second": 0,
                },
                {
                    "team_id": 10,
                    "event_type": "Pass",
                    "location_x": 30.0,
                    "end_location_x": 55.0,
                    "match_id": 1,
                    "minute": 15,
                    "second": 0,
                },
                {
                    "team_id": 10,
                    "event_type": "Pass",
                    "location_x": 50.0,
                    "end_location_x": 52.0,
                    "match_id": 1,
                    "minute": 20,
                    "second": 0,
                },
            ]
        )
        result = identify_space_creation_events(events, team_id=10)
        assert len(result) == 2  # Two progressive events


# =============================================================================
# TESTS: Video Alignment
# =============================================================================


class TestVideoAlignment:
    """Tests for video timestamp alignment."""

    def test_match_clock_to_video_first_half(self) -> None:
        from football_analytics.analysis.video_alignment import (
            VideoConfig,
            match_clock_to_video_time,
        )

        config = VideoConfig(video_start_offset=30.0)
        # Kick-off (0:00)
        assert match_clock_to_video_time(0, 0, 1, config) == 30.0
        # 10th minute
        assert match_clock_to_video_time(10, 0, 1, config) == 630.0

    def test_seconds_to_timecode(self) -> None:
        from football_analytics.analysis.video_alignment import seconds_to_timecode

        assert seconds_to_timecode(0.0) == "00:00:00.00"
        assert seconds_to_timecode(3661.5, 25.0) == "01:01:01.12"

    def test_timecode_to_seconds(self) -> None:
        from football_analytics.analysis.video_alignment import timecode_to_seconds

        assert timecode_to_seconds("00:00:00.00") == 0.0
        assert timecode_to_seconds("01:00:00.00") == 3600.0

    def test_generate_clips(self) -> None:
        from football_analytics.analysis.video_alignment import (
            generate_clips_from_events,
        )

        events = pd.DataFrame(
            [
                {
                    "event_id": "abc",
                    "event_type": "Shot",
                    "player_name": "Messi",
                    "minute": 25,
                    "second": 30,
                    "period": 1,
                    "xg": 0.3,
                    "shot_outcome": "Goal",
                },
            ]
        )
        clips = generate_clips_from_events(events, event_types=["Shot"])
        assert len(clips) == 1
        assert clips[0].player_name == "Messi"
        assert clips[0].clip_start < clips[0].video_start_time

    def test_calibrate_alignment(self) -> None:
        from football_analytics.analysis.video_alignment import calibrate_alignment

        refs = [
            {"minute": 0, "second": 0, "period": 1, "video_timestamp": 32.0},
            {"minute": 45, "second": 0, "period": 1, "video_timestamp": 2732.0},
        ]
        cal = calibrate_alignment(refs)
        assert cal.confidence > 0.5
        assert abs(cal.computed_offset) < 50  # Reasonable offset

    def test_export_ffmpeg(self) -> None:
        from football_analytics.analysis.video_alignment import (
            export_ffmpeg_clip_list,
            generate_clips_from_events,
        )

        events = pd.DataFrame(
            [
                {
                    "event_id": "abc",
                    "event_type": "Shot",
                    "player_name": "Player",
                    "minute": 10,
                    "second": 0,
                    "period": 1,
                    "xg": 0.2,
                    "shot_outcome": "Saved",
                },
            ]
        )
        clips = generate_clips_from_events(events)
        script = export_ffmpeg_clip_list(clips, "match.mp4")
        assert "ffmpeg" in script
        assert "match.mp4" in script

    def test_export_srt(self) -> None:
        from football_analytics.analysis.video_alignment import (
            export_srt_subtitles,
            generate_clips_from_events,
        )

        events = pd.DataFrame(
            [
                {
                    "event_id": "x",
                    "event_type": "Goal",
                    "player_name": "Scorer",
                    "minute": 55,
                    "second": 20,
                    "period": 2,
                    "xg": 0.5,
                    "shot_outcome": "Goal",
                },
            ]
        )
        clips = generate_clips_from_events(events)
        srt = export_srt_subtitles(clips)
        assert "-->" in srt
