"""Tests for new enhancement modules: xG model, similarity, cache, tracking."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

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
# TESTS: Parquet Cache
# =============================================================================


class TestParquetCache:
    """Tests for the Parquet caching layer."""

    def test_cache_miss_then_hit(self, tmp_path: Path) -> None:
        """First call should miss, second should hit."""
        import football_analytics.cache as cache_mod
        from football_analytics.cache import cached_query

        # Redirect cache to temp dir
        original_dir = cache_mod.CACHE_DIR
        cache_mod.CACHE_DIR = tmp_path

        call_count = 0

        def mock_query(x: int = 0) -> pd.DataFrame:
            nonlocal call_count
            call_count += 1
            return pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})

        # First call — cache miss
        result1 = cached_query("test", mock_query, x=1)
        assert call_count == 1
        assert len(result1) == 3

        # Second call — cache hit (query_fn should NOT be called again)
        result2 = cached_query("test", mock_query, x=1)
        assert call_count == 1  # Not called again
        assert result1.equals(result2)

        # Restore
        cache_mod.CACHE_DIR = original_dir

    def test_invalidate_cache(self, tmp_path: Path) -> None:
        """Invalidation should remove cached files."""
        import football_analytics.cache as cache_mod
        from football_analytics.cache import cached_query, invalidate_cache

        original_dir = cache_mod.CACHE_DIR
        cache_mod.CACHE_DIR = tmp_path

        cached_query("test_inv", lambda: pd.DataFrame({"x": [1]}))
        count = invalidate_cache("test_inv")
        assert count == 1

        cache_mod.CACHE_DIR = original_dir


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
