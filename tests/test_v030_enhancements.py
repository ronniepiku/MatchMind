"""Tests for v0.3.0 enhancements — possession chains, set pieces,
advanced xG, simulation, development tracking, spatial, video alignment, API.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# ============================================================================
# Possession Chain Tests
# ============================================================================


class TestPossessionChains:
    """Tests for possession chain extraction and analysis."""

    @pytest.fixture
    def sample_events(self) -> pd.DataFrame:
        """Create sample event data for two possessions."""
        return pd.DataFrame([
            # Possession 1: short build-up ending in shot
            {"match_id": 1, "possession": 1, "team_id": 10, "player_id": 101,
             "event_type": "Pass", "minute": 5, "second": 10, "location_x": 35.0,
             "location_y": 40.0, "end_location_x": 50.0, "end_location_y": 45.0,
             "pass_outcome": None, "pass_length": 16.0, "play_pattern": "From Open Play",
             "xg": None, "shot_outcome": None, "key_pass": False},
            {"match_id": 1, "possession": 1, "team_id": 10, "player_id": 102,
             "event_type": "Pass", "minute": 5, "second": 15, "location_x": 50.0,
             "location_y": 45.0, "end_location_x": 70.0, "end_location_y": 40.0,
             "pass_outcome": None, "pass_length": 21.0, "play_pattern": "From Open Play",
             "xg": None, "shot_outcome": None, "key_pass": False},
            {"match_id": 1, "possession": 1, "team_id": 10, "player_id": 103,
             "event_type": "Pass", "minute": 5, "second": 20, "location_x": 70.0,
             "location_y": 40.0, "end_location_x": 95.0, "end_location_y": 38.0,
             "pass_outcome": None, "pass_length": 25.0, "play_pattern": "From Open Play",
             "xg": None, "shot_outcome": None, "key_pass": True},
            {"match_id": 1, "possession": 1, "team_id": 10, "player_id": 104,
             "event_type": "Shot", "minute": 5, "second": 23, "location_x": 95.0,
             "location_y": 38.0, "end_location_x": 120.0, "end_location_y": 40.0,
             "pass_outcome": None, "pass_length": None, "play_pattern": "From Open Play",
             "xg": 0.15, "shot_outcome": "Saved", "key_pass": False},
            # Possession 2: counter attack ending in goal
            {"match_id": 1, "possession": 2, "team_id": 10, "player_id": 101,
             "event_type": "Pass", "minute": 10, "second": 5, "location_x": 25.0,
             "location_y": 50.0, "end_location_x": 80.0, "end_location_y": 35.0,
             "pass_outcome": None, "pass_length": 57.0, "play_pattern": "From Open Play",
             "xg": None, "shot_outcome": None, "key_pass": False},
            {"match_id": 1, "possession": 2, "team_id": 10, "player_id": 105,
             "event_type": "Shot", "minute": 10, "second": 10, "location_x": 105.0,
             "location_y": 40.0, "end_location_x": 120.0, "end_location_y": 40.0,
             "pass_outcome": None, "pass_length": None, "play_pattern": "From Open Play",
             "xg": 0.35, "shot_outcome": "Goal", "key_pass": False},
        ])

    def test_extract_chains(self, sample_events: pd.DataFrame) -> None:
        from football_analytics.analysis.possession_chains import extract_possession_chains

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
        from football_analytics.analysis.possession_chains import extract_possession_chains

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


# ============================================================================
# Set Piece Tests
# ============================================================================


class TestSetPieces:
    """Tests for set-piece extraction and analysis."""

    @pytest.fixture
    def corner_events(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"match_id": 1, "possession": 5, "team_id": 10, "player_id": 101,
             "event_type": "Pass", "minute": 30, "second": 0, "location_x": 120.0,
             "location_y": 0.0, "end_location_x": 115.0, "end_location_y": 38.0,
             "pass_outcome": None, "pass_type": "Inswinging", "play_pattern": "From Corner",
             "xg": None, "shot_outcome": None, "player_name": "Corner Taker"},
            {"match_id": 1, "possession": 5, "team_id": 10, "player_id": 102,
             "event_type": "Shot", "minute": 30, "second": 3, "location_x": 113.0,
             "location_y": 39.0, "end_location_x": 120.0, "end_location_y": 40.0,
             "pass_outcome": None, "pass_type": None, "play_pattern": "From Corner",
             "xg": 0.08, "shot_outcome": "Goal", "player_name": "Header Scorer"},
        ])

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


# ============================================================================
# Advanced xG Model Tests
# ============================================================================


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

        return pd.DataFrame({
            "location_x": locations_x,
            "location_y": locations_y,
            "shot_body_part": rng.choice(["Foot", "Head"], n, p=[0.75, 0.25]),
            "under_pressure": rng.choice([True, False], n, p=[0.3, 0.7]),
            "play_pattern": "From Open Play",
            "shot_type": rng.choice(["Open Play", "Penalty", "Free Kick"], n, p=[0.88, 0.07, 0.05]),
            "shot_outcome": np.where(goals, "Goal", "Off T"),
            "minute": rng.integers(1, 90, n),
        })

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
        from football_analytics.analysis.xg_model_advanced import train_advanced_xg_model

        result = train_advanced_xg_model(
            shot_data, backend="hist", tune_hyperparams=False, calibrate=False
        )
        assert result.metrics.roc_auc > 0.55  # Better than random
        assert 0 <= result.metrics.brier_score <= 0.25
        assert len(result.cv_predictions) == len(shot_data)

    def test_predict_advanced(self, shot_data: pd.DataFrame) -> None:
        from football_analytics.analysis.xg_model_advanced import (
            predict_advanced_xg,
            train_advanced_xg_model,
        )

        result = train_advanced_xg_model(
            shot_data, backend="hist", tune_hyperparams=False, calibrate=False
        )
        preds = predict_advanced_xg(result.model, shot_data.head(10))
        assert len(preds) == 10
        assert all(0 <= p <= 1 for p in preds)

    def test_feature_importance(self, shot_data: pd.DataFrame) -> None:
        from football_analytics.analysis.xg_model_advanced import train_advanced_xg_model

        result = train_advanced_xg_model(
            shot_data, backend="hist", tune_hyperparams=False, calibrate=False
        )
        assert not result.feature_importance.empty
        assert "feature" in result.feature_importance.columns
        assert "importance" in result.feature_importance.columns


# ============================================================================
# Match Simulation Tests
# ============================================================================


class TestMatchSimulation:
    """Tests for Monte Carlo match simulation."""

    def test_simulate_match_basic(self) -> None:
        from football_analytics.analysis.simulation import simulate_match

        result = simulate_match(home_xg=1.5, away_xg=1.0, n_simulations=10000)

        # Probabilities should sum to ~1
        total = result.home_win_prob + result.draw_prob + result.away_win_prob
        assert abs(total - 1.0) < 0.01

        # Home team with higher xG should win more often
        assert result.home_win_prob > result.away_win_prob

    def test_simulate_match_high_xg(self) -> None:
        from football_analytics.analysis.simulation import simulate_match

        result = simulate_match(home_xg=3.0, away_xg=0.5, n_simulations=10000)
        assert result.home_win_prob > 0.7  # Strong favourite

    def test_expected_goals_match_input(self) -> None:
        from football_analytics.analysis.simulation import simulate_match

        result = simulate_match(home_xg=2.0, away_xg=1.0, n_simulations=50000)
        # Expected goals should be close to input xG
        assert abs(result.expected_home_goals - 2.0) < 0.2
        assert abs(result.expected_away_goals - 1.0) < 0.2

    def test_over_under_probabilities(self) -> None:
        from football_analytics.analysis.simulation import simulate_match

        result = simulate_match(home_xg=2.0, away_xg=2.0, n_simulations=10000)
        # High-scoring match should have high over 2.5 probability
        assert result.over_2_5_prob > 0.5

    def test_simulate_remaining_match(self) -> None:
        from football_analytics.analysis.simulation import simulate_remaining_match

        result = simulate_remaining_match(
            current_home_goals=2,
            current_away_goals=0,
            minutes_played=70,
            home_xg_remaining=0.3,
            away_xg_remaining=0.5,
        )
        # Team leading 2-0 with 20 mins left should usually win
        assert result.home_win_prob > 0.7

    def test_format_report(self) -> None:
        from football_analytics.analysis.simulation import (
            format_simulation_report,
            simulate_match,
        )

        result = simulate_match(home_xg=1.5, away_xg=1.2, home_team="Arsenal", away_team="Chelsea")
        report = format_simulation_report(result)
        assert "Arsenal" in report
        assert "Chelsea" in report
        assert "Over 2.5" in report


# ============================================================================
# Player Development Tests
# ============================================================================


class TestPlayerDevelopment:
    """Tests for player development tracking."""

    @pytest.fixture
    def per90_data(self) -> pd.DataFrame:
        """Create multi-season per-90 data for a developing player."""
        return pd.DataFrame([
            {"player_id": 1, "season_id": 1, "matches": 20, "minutes_played": 1400,
             "goals_per_90": 0.10, "xg_per_90": 0.15, "shots_per_90": 2.0,
             "xa_per_90": 0.05, "successful_dribbles_per_90": 1.0, "pressures_per_90": 8.0},
            {"player_id": 1, "season_id": 2, "matches": 30, "minutes_played": 2200,
             "goals_per_90": 0.20, "xg_per_90": 0.25, "shots_per_90": 2.8,
             "xa_per_90": 0.08, "successful_dribbles_per_90": 1.3, "pressures_per_90": 9.0},
            {"player_id": 1, "season_id": 3, "matches": 35, "minutes_played": 2800,
             "goals_per_90": 0.35, "xg_per_90": 0.38, "shots_per_90": 3.5,
             "xa_per_90": 0.12, "successful_dribbles_per_90": 1.8, "pressures_per_90": 10.0},
        ])

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


# ============================================================================
# Spatial Dominance Tests
# ============================================================================


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

        defenders = np.array([
            [20.0, 30.0], [25.0, 45.0], [30.0, 20.0], [30.0, 55.0]
        ])
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
        compact = np.array([
            [40.0, 30.0], [42.0, 32.0], [38.0, 34.0],
            [41.0, 36.0], [43.0, 28.0], [5.0, 34.0],  # GK
        ])
        result = compute_team_compactness(compact, exclude_gk=True)
        assert result["compactness_area"] > 0
        assert result["team_length"] < 10  # Very compact

    def test_space_creation_events(self) -> None:
        from football_analytics.analysis.spatial import identify_space_creation_events

        events = pd.DataFrame([
            {"team_id": 10, "event_type": "Carry", "location_x": 40.0,
             "carry_end_x": 60.0, "match_id": 1, "minute": 10, "second": 0},
            {"team_id": 10, "event_type": "Pass", "location_x": 30.0,
             "end_location_x": 55.0, "match_id": 1, "minute": 15, "second": 0},
            {"team_id": 10, "event_type": "Pass", "location_x": 50.0,
             "end_location_x": 52.0, "match_id": 1, "minute": 20, "second": 0},
        ])
        result = identify_space_creation_events(events, team_id=10)
        assert len(result) == 2  # Two progressive events


# ============================================================================
# Video Alignment Tests
# ============================================================================


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
        from football_analytics.analysis.video_alignment import generate_clips_from_events

        events = pd.DataFrame([
            {"event_id": "abc", "event_type": "Shot", "player_name": "Messi",
             "minute": 25, "second": 30, "period": 1, "xg": 0.3, "shot_outcome": "Goal"},
        ])
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

        events = pd.DataFrame([
            {"event_id": "abc", "event_type": "Shot", "player_name": "Player",
             "minute": 10, "second": 0, "period": 1, "xg": 0.2, "shot_outcome": "Saved"},
        ])
        clips = generate_clips_from_events(events)
        script = export_ffmpeg_clip_list(clips, "match.mp4")
        assert "ffmpeg" in script
        assert "match.mp4" in script

    def test_export_srt(self) -> None:
        from football_analytics.analysis.video_alignment import (
            export_srt_subtitles,
            generate_clips_from_events,
        )

        events = pd.DataFrame([
            {"event_id": "x", "event_type": "Goal", "player_name": "Scorer",
             "minute": 55, "second": 20, "period": 2, "xg": 0.5, "shot_outcome": "Goal"},
        ])
        clips = generate_clips_from_events(events)
        srt = export_srt_subtitles(clips)
        assert "-->" in srt


# ============================================================================
# API Tests
# ============================================================================


class TestAPI:
    """Tests for FastAPI endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from football_analytics.api import app
        return TestClient(app)

    def test_health_check(self, client) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_xg_predict(self, client) -> None:
        response = client.post("/api/v1/xg/predict", json={
            "location_x": 105.0,
            "location_y": 40.0,
            "shot_body_part": "Foot",
            "under_pressure": False,
        })
        assert response.status_code == 200
        data = response.json()
        assert 0 <= data["xg"] <= 1
        assert data["distance_to_goal"] > 0

    def test_xg_predict_penalty(self, client) -> None:
        response = client.post("/api/v1/xg/predict", json={
            "location_x": 108.0,
            "location_y": 40.0,
            "shot_body_part": "Foot",
            "under_pressure": False,
            "shot_type": "Penalty",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["xg"] > 0.7  # Penalties should be high xG

    def test_simulate_match(self, client) -> None:
        response = client.post("/api/v1/simulation/match", json={
            "home_xg": 1.8,
            "away_xg": 1.2,
            "home_team": "Liverpool",
            "away_team": "Everton",
            "n_simulations": 1000,
        })
        assert response.status_code == 200
        data = response.json()
        total = data["home_win_prob"] + data["draw_prob"] + data["away_win_prob"]
        assert abs(total - 1.0) < 0.02

    def test_xg_predict_validation(self, client) -> None:
        # location_x out of range
        response = client.post("/api/v1/xg/predict", json={
            "location_x": 200.0,  # Invalid
            "location_y": 40.0,
        })
        assert response.status_code == 422  # Validation error
