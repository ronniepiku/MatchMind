"""Match simulation — Monte Carlo simulation for outcome prediction.

Uses team xG data to simulate match outcomes thousands of times,
providing probability distributions for:
- Win/draw/loss probabilities
- Expected scorelines
- Over/under goal thresholds
- First-team-to-score probabilities
- Comeback probabilities

Useful for:
- Pre-match strategy (how likely is a draw? should we attack?)
- In-match decision support (given current score and minutes left)
- Season projections (simulate remaining fixtures)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Default number of simulations
_DEFAULT_SIMULATIONS = 10_000


@dataclass
class MatchSimulationResult:
    """Results from a Monte Carlo match simulation."""

    home_team: str
    away_team: str
    n_simulations: int
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    expected_home_goals: float
    expected_away_goals: float
    most_likely_score: tuple[int, int]
    scoreline_probabilities: dict[tuple[int, int], float]
    over_1_5_prob: float
    over_2_5_prob: float
    over_3_5_prob: float
    btts_prob: float  # Both teams to score
    first_goal_home_prob: float
    home_goals_distribution: np.ndarray
    away_goals_distribution: np.ndarray


def simulate_match(
    home_xg: float,
    away_xg: float,
    home_team: str = "Home",
    away_team: str = "Away",
    n_simulations: int = _DEFAULT_SIMULATIONS,
    xg_variance: float = 0.15,
    home_advantage_factor: float = 1.0,
) -> MatchSimulationResult:
    """Simulate a match using expected goals (xG) as Poisson parameters.

    The model assumes goals follow a Poisson process, which is well-established
    in football analytics literature (Dixon & Coles, 1997).

    Args:
        home_xg: Expected goals for home team (from model or historical average).
        away_xg: Expected goals for away team.
        home_team: Home team name.
        away_team: Away team name.
        n_simulations: Number of Monte Carlo simulations.
        xg_variance: Random variance added to xG per simulation (realism).
        home_advantage_factor: Multiplier for home xG (1.0 = no adjustment).

    Returns:
        MatchSimulationResult with full probability distributions.
    """
    rng = np.random.default_rng(seed=42)

    # Apply home advantage
    adj_home_xg = home_xg * home_advantage_factor

    # Simulate with per-match variance (team form noise)
    home_lambdas = np.maximum(0.1, rng.normal(adj_home_xg, xg_variance * adj_home_xg, n_simulations))
    away_lambdas = np.maximum(0.1, rng.normal(away_xg, xg_variance * away_xg, n_simulations))

    # Draw goals from Poisson distribution
    home_goals = rng.poisson(home_lambdas)
    away_goals = rng.poisson(away_lambdas)

    # Outcome probabilities
    home_wins = (home_goals > away_goals).mean()
    draws = (home_goals == away_goals).mean()
    away_wins = (home_goals < away_goals).mean()

    # Scoreline probabilities
    total_goals = home_goals + away_goals
    scorelines: dict[tuple[int, int], float] = {}
    for h in range(max(home_goals) + 1):
        for a in range(max(away_goals) + 1):
            prob = ((home_goals == h) & (away_goals == a)).mean()
            if prob > 0.001:
                scorelines[(h, a)] = round(float(prob), 4)

    most_likely = max(scorelines, key=scorelines.get)

    # Goal threshold probabilities
    over_1_5 = (total_goals > 1.5).mean()
    over_2_5 = (total_goals > 2.5).mean()
    over_3_5 = (total_goals > 3.5).mean()

    # Both teams to score
    btts = ((home_goals > 0) & (away_goals > 0)).mean()

    # First goal probability (simplified: proportional to xG)
    total_xg = adj_home_xg + away_xg
    first_goal_home = adj_home_xg / total_xg if total_xg > 0 else 0.5

    return MatchSimulationResult(
        home_team=home_team,
        away_team=away_team,
        n_simulations=n_simulations,
        home_win_prob=round(float(home_wins), 4),
        draw_prob=round(float(draws), 4),
        away_win_prob=round(float(away_wins), 4),
        expected_home_goals=round(float(home_goals.mean()), 2),
        expected_away_goals=round(float(away_goals.mean()), 2),
        most_likely_score=most_likely,
        scoreline_probabilities=scorelines,
        over_1_5_prob=round(float(over_1_5), 4),
        over_2_5_prob=round(float(over_2_5), 4),
        over_3_5_prob=round(float(over_3_5), 4),
        btts_prob=round(float(btts), 4),
        first_goal_home_prob=round(float(first_goal_home), 4),
        home_goals_distribution=home_goals,
        away_goals_distribution=away_goals,
    )


def simulate_match_minute_by_minute(
    home_xg_timeline: np.ndarray,
    away_xg_timeline: np.ndarray,
    home_team: str = "Home",
    away_team: str = "Away",
    n_simulations: int = _DEFAULT_SIMULATIONS,
) -> pd.DataFrame:
    """Simulate match with minute-by-minute xG accumulation.

    More granular than single-lambda simulation. Uses per-minute
    goal probabilities derived from xG timeline.

    Args:
        home_xg_timeline: Array of per-minute xG values (length ~90-120).
        away_xg_timeline: Array of per-minute xG values.
        home_team: Home team name.
        away_team: Away team name.
        n_simulations: Number of simulations.

    Returns:
        DataFrame with minute-by-minute win probability evolution.
    """
    rng = np.random.default_rng(seed=42)
    n_minutes = len(home_xg_timeline)

    # Simulate goals minute by minute
    # Each minute: probability of goal = per-minute xG
    home_scores = np.zeros((n_simulations, n_minutes), dtype=int)
    away_scores = np.zeros((n_simulations, n_minutes), dtype=int)

    for t in range(n_minutes):
        home_scores[:, t] = rng.binomial(1, min(home_xg_timeline[t], 0.5), n_simulations)
        away_scores[:, t] = rng.binomial(1, min(away_xg_timeline[t], 0.5), n_simulations)

    # Cumulative scores
    cum_home = np.cumsum(home_scores, axis=1)
    cum_away = np.cumsum(away_scores, axis=1)

    # Win probabilities at each minute
    records = []
    for t in range(n_minutes):
        home_leading = (cum_home[:, t] > cum_away[:, t]).mean()
        drawing = (cum_home[:, t] == cum_away[:, t]).mean()
        away_leading = (cum_home[:, t] < cum_away[:, t]).mean()

        records.append({
            "minute": t + 1,
            "home_win_prob": round(float(home_leading), 4),
            "draw_prob": round(float(drawing), 4),
            "away_win_prob": round(float(away_leading), 4),
            "avg_home_goals": round(float(cum_home[:, t].mean()), 2),
            "avg_away_goals": round(float(cum_away[:, t].mean()), 2),
        })

    return pd.DataFrame(records)


def simulate_remaining_match(
    current_home_goals: int,
    current_away_goals: int,
    minutes_played: int,
    home_xg_remaining: float,
    away_xg_remaining: float,
    home_team: str = "Home",
    away_team: str = "Away",
    n_simulations: int = _DEFAULT_SIMULATIONS,
) -> MatchSimulationResult:
    """Simulate the remainder of a match given current state.

    Useful for in-match tactical decisions:
    "What's the probability of winning from here?"

    Args:
        current_home_goals: Goals scored by home team so far.
        current_away_goals: Goals scored by away team so far.
        minutes_played: Minutes already played.
        home_xg_remaining: Expected xG for home in remaining time.
        away_xg_remaining: Expected xG for away in remaining time.
        home_team: Home team name.
        away_team: Away team name.
        n_simulations: Number of simulations.

    Returns:
        MatchSimulationResult for the full match (current + simulated remainder).
    """
    rng = np.random.default_rng(seed=42)

    # Simulate remaining goals
    home_additional = rng.poisson(home_xg_remaining, n_simulations)
    away_additional = rng.poisson(away_xg_remaining, n_simulations)

    # Total goals (current + simulated)
    home_total = current_home_goals + home_additional
    away_total = current_away_goals + away_additional

    home_wins = (home_total > away_total).mean()
    draws = (home_total == away_total).mean()
    away_wins = (home_total < away_total).mean()

    total_goals = home_total + away_total

    scorelines: dict[tuple[int, int], float] = {}
    for h in range(int(home_total.max()) + 1):
        for a in range(int(away_total.max()) + 1):
            prob = ((home_total == h) & (away_total == a)).mean()
            if prob > 0.001:
                scorelines[(h, a)] = round(float(prob), 4)

    most_likely = max(scorelines, key=scorelines.get) if scorelines else (current_home_goals, current_away_goals)

    return MatchSimulationResult(
        home_team=home_team,
        away_team=away_team,
        n_simulations=n_simulations,
        home_win_prob=round(float(home_wins), 4),
        draw_prob=round(float(draws), 4),
        away_win_prob=round(float(away_wins), 4),
        expected_home_goals=round(float(home_total.mean()), 2),
        expected_away_goals=round(float(away_total.mean()), 2),
        most_likely_score=most_likely,
        scoreline_probabilities=scorelines,
        over_1_5_prob=round(float((total_goals > 1.5).mean()), 4),
        over_2_5_prob=round(float((total_goals > 2.5).mean()), 4),
        over_3_5_prob=round(float((total_goals > 3.5).mean()), 4),
        btts_prob=round(float(((home_total > 0) & (away_total > 0)).mean()), 4),
        first_goal_home_prob=0.5,  # N/A for in-match
        home_goals_distribution=home_total,
        away_goals_distribution=away_total,
    )


def simulate_season(
    fixtures: pd.DataFrame,
    team_xg_data: pd.DataFrame,
    n_simulations: int = 1_000,
) -> pd.DataFrame:
    """Simulate remaining season fixtures to project final standings.

    Args:
        fixtures: DataFrame with home_team_id, away_team_id columns.
        team_xg_data: DataFrame with team_id, avg_xg_for, avg_xg_against.
        n_simulations: Simulations per match.

    Returns:
        DataFrame with projected points, goal difference, and finish
        probabilities for each team.
    """
    rng = np.random.default_rng(seed=42)

    # Build team strength lookup
    team_strength = {}
    for _, row in team_xg_data.iterrows():
        team_strength[row["team_id"]] = {
            "xg_for": row["avg_xg_for"],
            "xg_against": row["avg_xg_against"],
        }

    # Simulate all fixtures
    team_points: dict[int, list[int]] = {tid: [] for tid in team_strength}
    team_gd: dict[int, list[int]] = {tid: [] for tid in team_strength}

    for _ in range(n_simulations):
        sim_points: dict[int, int] = {tid: 0 for tid in team_strength}
        sim_gd: dict[int, int] = {tid: 0 for tid in team_strength}

        for _, match in fixtures.iterrows():
            home_id = match["home_team_id"]
            away_id = match["away_team_id"]

            if home_id not in team_strength or away_id not in team_strength:
                continue

            home_xg = (team_strength[home_id]["xg_for"] + team_strength[away_id]["xg_against"]) / 2
            away_xg = (team_strength[away_id]["xg_for"] + team_strength[home_id]["xg_against"]) / 2

            home_goals = rng.poisson(home_xg * 1.1)  # Home advantage
            away_goals = rng.poisson(away_xg)

            sim_gd[home_id] += home_goals - away_goals
            sim_gd[away_id] += away_goals - home_goals

            if home_goals > away_goals:
                sim_points[home_id] += 3
            elif home_goals == away_goals:
                sim_points[home_id] += 1
                sim_points[away_id] += 1
            else:
                sim_points[away_id] += 3

        for tid in team_strength:
            team_points[tid].append(sim_points[tid])
            team_gd[tid].append(sim_gd[tid])

    # Compile results
    results = []
    for tid in team_strength:
        points_arr = np.array(team_points[tid])
        gd_arr = np.array(team_gd[tid])
        results.append({
            "team_id": tid,
            "avg_points": round(float(points_arr.mean()), 1),
            "median_points": float(np.median(points_arr)),
            "points_std": round(float(points_arr.std()), 1),
            "avg_gd": round(float(gd_arr.mean()), 1),
            "top_4_prob": round(float((points_arr >= np.percentile(points_arr, 75)).mean()), 3),
            "title_prob": round(float((points_arr >= points_arr.max() * 0.95).mean()), 3),
        })

    return pd.DataFrame(results).sort_values("avg_points", ascending=False)


def format_simulation_report(result: MatchSimulationResult) -> str:
    """Format simulation results as a readable report.

    Args:
        result: MatchSimulationResult from simulate_match.

    Returns:
        Formatted string report.
    """
    lines = [
        f"Match Simulation: {result.home_team} vs {result.away_team}",
        f"{'═' * 50}",
        f"Simulations: {result.n_simulations:,}",
        "",
        "Outcome Probabilities:",
        f"  {result.home_team} win: {result.home_win_prob:.1%}",
        f"  Draw:             {result.draw_prob:.1%}",
        f"  {result.away_team} win: {result.away_win_prob:.1%}",
        "",
        "Expected Goals:",
        f"  {result.home_team}: {result.expected_home_goals}",
        f"  {result.away_team}: {result.expected_away_goals}",
        "",
        f"Most likely score: {result.most_likely_score[0]}-{result.most_likely_score[1]}",
        "",
        "Market Probabilities:",
        f"  Over 1.5 goals: {result.over_1_5_prob:.1%}",
        f"  Over 2.5 goals: {result.over_2_5_prob:.1%}",
        f"  Over 3.5 goals: {result.over_3_5_prob:.1%}",
        f"  BTTS:           {result.btts_prob:.1%}",
        "",
        "Top Scorelines:",
    ]

    top_scores = sorted(result.scoreline_probabilities.items(), key=lambda x: x[1], reverse=True)[:5]
    for (h, a), prob in top_scores:
        lines.append(f"  {h}-{a}: {prob:.1%}")

    return "\n".join(lines)
