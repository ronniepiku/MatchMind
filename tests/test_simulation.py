"""Tests for the Monte Carlo match simulation engine."""

from __future__ import annotations

import pytest

from football_analytics.analysis.simulation import simulate_match


class TestSimulateMatch:
    """Tests for simulate_match function."""

    def test_probabilities_sum_to_one(self) -> None:
        result = simulate_match(home_xg=1.5, away_xg=1.2, n_simulations=10000)
        prob_sum = result.home_win_prob + result.draw_prob + result.away_win_prob
        assert abs(prob_sum - 1.0) < 0.001

    def test_seed_produces_deterministic_results(self) -> None:
        result1 = simulate_match(home_xg=2.0, away_xg=1.0, n_simulations=5000, seed=42)
        result2 = simulate_match(home_xg=2.0, away_xg=1.0, n_simulations=5000, seed=42)
        assert result1.home_win_prob == result2.home_win_prob
        assert result1.draw_prob == result2.draw_prob
        assert result1.away_win_prob == result2.away_win_prob

    def test_no_seed_produces_varying_results(self) -> None:
        """Without a seed, results should vary (probabilistically)."""
        results = [
            simulate_match(home_xg=1.5, away_xg=1.5, n_simulations=1000)
            for _ in range(5)
        ]
        # With 1000 sims and no seed, home_win_prob should not be identical across all runs
        home_probs = [r.home_win_prob for r in results]
        assert len(set(home_probs)) > 1, "All runs produced identical results without a seed"

    def test_higher_xg_favours_team(self) -> None:
        result = simulate_match(home_xg=3.0, away_xg=0.5, n_simulations=10000, seed=123)
        assert result.home_win_prob > result.away_win_prob
        assert result.home_win_prob > 0.7

    def test_home_advantage_factor(self) -> None:
        neutral = simulate_match(home_xg=1.5, away_xg=1.5, home_advantage_factor=1.0, n_simulations=10000, seed=99)
        boosted = simulate_match(home_xg=1.5, away_xg=1.5, home_advantage_factor=1.3, n_simulations=10000, seed=99)
        assert boosted.home_win_prob > neutral.home_win_prob

    def test_over_under_thresholds_monotonic(self) -> None:
        result = simulate_match(home_xg=2.0, away_xg=1.5, n_simulations=10000, seed=7)
        assert result.over_1_5_prob >= result.over_2_5_prob
        assert result.over_2_5_prob >= result.over_3_5_prob

    def test_btts_probability_reasonable(self) -> None:
        result = simulate_match(home_xg=2.0, away_xg=1.5, n_simulations=10000, seed=7)
        assert 0.0 <= result.btts_prob <= 1.0

    def test_most_likely_score_is_tuple(self) -> None:
        result = simulate_match(home_xg=1.5, away_xg=1.0, n_simulations=5000, seed=42)
        assert len(result.most_likely_score) == 2
        assert all(isinstance(g, (int,)) for g in result.most_likely_score)

    def test_team_names_preserved(self) -> None:
        result = simulate_match(
            home_xg=1.5,
            away_xg=1.0,
            home_team="Arsenal",
            away_team="Chelsea",
            n_simulations=100,
            seed=1,
        )
        assert result.home_team == "Arsenal"
        assert result.away_team == "Chelsea"

    def test_expected_goals_reasonable(self) -> None:
        result = simulate_match(home_xg=2.0, away_xg=1.0, n_simulations=10000, seed=42)
        # Expected goals should be close to input xG
        assert abs(result.expected_home_goals - 2.0) < 0.3
        assert abs(result.expected_away_goals - 1.0) < 0.3

    def test_minimum_simulations(self) -> None:
        """Should work with minimum number of simulations."""
        result = simulate_match(home_xg=1.0, away_xg=1.0, n_simulations=100, seed=5)
        assert result.n_simulations == 100
        assert result.home_win_prob >= 0
