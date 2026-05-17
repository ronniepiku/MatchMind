"""Player development tracking — longitudinal analysis of player progression.

Tracks player metrics over multiple seasons to identify:
- Development trajectories (improving, plateauing, declining)
- Breakout seasons / regression candidates
- Age curves (expected development by position)
- Academy talent identification

Particularly valuable for:
- Recruitment: Identify players on upward trajectories before market catches on
- Squad planning: Predict when players will peak/decline
- Academy: Track U23 development against benchmarks
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# Typical peak ages by position group (from academic research)
_PEAK_AGE_RANGES = {
    "goalkeeper": (28, 33),
    "defender": (26, 31),
    "midfielder": (25, 30),
    "forward": (24, 29),
}

# Key metrics tracked per position
_POSITION_METRICS = {
    "goalkeeper": ["saves_per_match", "clean_sheet_rate", "pass_accuracy"],
    "defender": [
        "tackles_per_90", "interceptions_per_90", "aerial_wins_per_90",
        "progressive_carries_per_90", "pass_accuracy",
    ],
    "midfielder": [
        "passes_completed_per_90", "key_passes_per_90", "progressive_passes_per_90",
        "xg_per_90", "xa_per_90", "pressures_per_90",
    ],
    "forward": [
        "goals_per_90", "xg_per_90", "shots_per_90", "xa_per_90",
        "successful_dribbles_per_90", "pressures_per_90",
    ],
}


@dataclass
class DevelopmentProfile:
    """Player development profile over time."""

    player_id: int
    player_name: str
    position_group: str
    seasons: list[int]
    ages: list[int] | None
    metrics_by_season: pd.DataFrame
    trend_slopes: dict[str, float]
    trajectory: str  # improving, declining, stable, breakout, regression
    percentile_changes: dict[str, float]
    predicted_peak_age: int | None = None
    minutes_played: list[int] | None = None


def compute_per90_metrics(
    events_df: pd.DataFrame,
    lineups_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute per-90-minute metrics for each player-season.

    Args:
        events_df: Event-level data with match_id, player_id, team_id, season_id.
        lineups_df: Optional lineup data with minutes_played per match.

    Returns:
        DataFrame with per-90 metrics per player per season.
    """
    if "season_id" not in events_df.columns:
        raise ValueError("events_df must contain 'season_id' column")

    # Aggregate raw counts per player per season
    grouped = events_df.groupby(["player_id", "season_id"])

    agg = grouped.agg(
        matches=("match_id", "nunique"),
        passes_completed=("event_type", lambda x: ((x == "Pass") & events_df.loc[x.index, "pass_outcome"].isna()).sum()),
        passes_attempted=("event_type", lambda x: (x == "Pass").sum()),
        shots=("event_type", lambda x: (x == "Shot").sum()),
        goals=("shot_outcome", lambda x: (x == "Goal").sum()),
        xg_total=("xg", "sum"),
        xa_total=("xa", "sum"),
        key_passes=("key_pass", "sum"),
        assists=("assist", "sum"),
        pressures=("event_type", lambda x: (x == "Pressure").sum()),
        tackles=("event_type", lambda x: (x == "Tackle").sum()),
        interceptions=("event_type", lambda x: (x == "Interception").sum()),
        dribbles_completed=("dribble_outcome", lambda x: (x == "Complete").sum()),
        carries=("event_type", lambda x: (x == "Carry").sum()),
    ).reset_index()

    # Estimate minutes (matches × 90 if no lineup data)
    if lineups_df is not None and "minutes_played" in lineups_df.columns:
        minutes = lineups_df.groupby(["player_id", "season_id"])["minutes_played"].sum().reset_index()
        agg = agg.merge(minutes, on=["player_id", "season_id"], how="left")
        agg["minutes_played"] = agg["minutes_played"].fillna(agg["matches"] * 70)
    else:
        agg["minutes_played"] = agg["matches"] * 70  # Conservative estimate

    # Per-90 normalisation
    per90_factor = 90.0 / agg["minutes_played"].clip(lower=90)

    agg["goals_per_90"] = agg["goals"] * per90_factor
    agg["xg_per_90"] = agg["xg_total"] * per90_factor
    agg["xa_per_90"] = agg["xa_total"] * per90_factor
    agg["shots_per_90"] = agg["shots"] * per90_factor
    agg["key_passes_per_90"] = agg["key_passes"] * per90_factor
    agg["passes_completed_per_90"] = agg["passes_completed"] * per90_factor
    agg["pressures_per_90"] = agg["pressures"] * per90_factor
    agg["tackles_per_90"] = agg["tackles"] * per90_factor
    agg["interceptions_per_90"] = agg["interceptions"] * per90_factor
    agg["successful_dribbles_per_90"] = agg["dribbles_completed"] * per90_factor
    agg["progressive_carries_per_90"] = agg["carries"] * per90_factor * 0.3  # Estimate
    agg["pass_accuracy"] = (
        agg["passes_completed"] / agg["passes_attempted"].clip(lower=1)
    )

    return agg


def compute_development_profile(
    per90_df: pd.DataFrame,
    player_id: int,
    position_group: str = "midfielder",
    player_name: str | None = None,
    ages: list[int] | None = None,
) -> DevelopmentProfile:
    """Compute a development profile for a single player.

    Analyses trends across seasons to classify trajectory.

    Args:
        per90_df: Per-90 metrics DataFrame (from compute_per90_metrics).
        player_id: Player to analyse.
        position_group: Position for relevant metrics selection.
        player_name: Player name (for display).
        ages: Optional list of player ages corresponding to each season.

    Returns:
        DevelopmentProfile with trends and trajectory classification.
    """
    player_data = per90_df[per90_df["player_id"] == player_id].sort_values("season_id")

    if player_data.empty:
        raise ValueError(f"No data found for player_id={player_id}")

    seasons = player_data["season_id"].tolist()
    relevant_metrics = _POSITION_METRICS.get(position_group, _POSITION_METRICS["midfielder"])

    # Compute trend slopes (linear regression over seasons)
    trend_slopes = {}
    for metric in relevant_metrics:
        if metric in player_data.columns:
            values = player_data[metric].fillna(0).values
            if len(values) >= 2:
                x = np.arange(len(values))
                slope, _, _, _, _ = stats.linregress(x, values)
                trend_slopes[metric] = round(float(slope), 4)

    # Percentile changes (first season vs last season)
    percentile_changes = {}
    if len(player_data) >= 2:
        for metric in relevant_metrics:
            if metric in player_data.columns:
                first_val = player_data[metric].iloc[0]
                last_val = player_data[metric].iloc[-1]
                if first_val > 0:
                    pct_change = (last_val - first_val) / first_val * 100
                    percentile_changes[metric] = round(float(pct_change), 1)

    # Classify trajectory
    trajectory = _classify_trajectory(trend_slopes, position_group)

    # Predict peak age
    peak_age = None
    if ages and position_group in _PEAK_AGE_RANGES:
        current_age = ages[-1] if ages else None
        peak_start, peak_end = _PEAK_AGE_RANGES[position_group]
        if current_age:
            peak_age = (peak_start + peak_end) // 2

    return DevelopmentProfile(
        player_id=player_id,
        player_name=player_name or f"Player {player_id}",
        position_group=position_group,
        seasons=seasons,
        ages=ages,
        metrics_by_season=player_data,
        trend_slopes=trend_slopes,
        trajectory=trajectory,
        percentile_changes=percentile_changes,
        predicted_peak_age=peak_age,
        minutes_played=player_data["minutes_played"].tolist() if "minutes_played" in player_data else None,
    )


def _classify_trajectory(slopes: dict[str, float], position: str) -> str:
    """Classify player trajectory based on metric trends."""
    if not slopes:
        return "stable"

    positive_trends = sum(1 for s in slopes.values() if s > 0.01)
    negative_trends = sum(1 for s in slopes.values() if s < -0.01)
    total = len(slopes)

    if total == 0:
        return "stable"

    positive_ratio = positive_trends / total
    negative_ratio = negative_trends / total

    # Strong trends
    avg_slope = np.mean(list(slopes.values()))
    if avg_slope > 0.05 and positive_ratio > 0.7:
        return "breakout"
    if avg_slope < -0.05 and negative_ratio > 0.7:
        return "regression"
    if positive_ratio > 0.6:
        return "improving"
    if negative_ratio > 0.6:
        return "declining"

    return "stable"


def identify_breakout_candidates(
    per90_df: pd.DataFrame,
    position_group: str = "forward",
    max_age: int = 23,
    min_seasons: int = 2,
    ages_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Identify young players with strong upward trajectories.

    Args:
        per90_df: Per-90 metrics DataFrame.
        position_group: Position group to filter.
        max_age: Maximum current age for "young" player.
        min_seasons: Minimum seasons of data required.
        ages_df: Optional DataFrame with player_id and current_age.

    Returns:
        DataFrame of breakout candidates ranked by improvement.
    """
    # Filter to players with enough data
    season_counts = per90_df.groupby("player_id")["season_id"].nunique()
    eligible = season_counts[season_counts >= min_seasons].index

    candidates = []
    for player_id in eligible:
        player_data = per90_df[per90_df["player_id"] == player_id].sort_values("season_id")

        # Age filter (if available)
        if ages_df is not None:
            age_row = ages_df[ages_df["player_id"] == player_id]
            if not age_row.empty and age_row.iloc[0].get("current_age", 99) > max_age:
                continue

        # Compute trajectory
        metrics = _POSITION_METRICS.get(position_group, _POSITION_METRICS["midfielder"])
        slopes = {}
        for metric in metrics:
            if metric in player_data.columns:
                values = player_data[metric].fillna(0).values
                if len(values) >= 2:
                    x = np.arange(len(values))
                    slope, _, _, _, _ = stats.linregress(x, values)
                    slopes[metric] = slope

        if not slopes:
            continue

        avg_improvement = np.mean(list(slopes.values()))
        trajectory = _classify_trajectory(slopes, position_group)

        if trajectory in ("improving", "breakout"):
            candidates.append({
                "player_id": player_id,
                "seasons_tracked": len(player_data),
                "trajectory": trajectory,
                "avg_improvement_slope": round(avg_improvement, 4),
                "key_improvements": {k: round(v, 4) for k, v in slopes.items() if v > 0.01},
            })

    result = pd.DataFrame(candidates)
    if not result.empty:
        result = result.sort_values("avg_improvement_slope", ascending=False)

    logger.info("Found %d breakout candidates from %d eligible players", len(result), len(eligible))
    return result


def compute_age_curve(
    per90_df: pd.DataFrame,
    ages_df: pd.DataFrame,
    metric: str = "xg_per_90",
    position_group: str | None = None,
) -> pd.DataFrame:
    """Compute average age curve for a given metric.

    Shows expected performance level at each age, useful for
    contextualising individual player performance.

    Args:
        per90_df: Per-90 metrics DataFrame.
        ages_df: DataFrame with player_id and age per season.
        metric: Metric to compute curve for.
        position_group: Optional position filter.

    Returns:
        DataFrame with age and average metric value.
    """
    merged = per90_df.merge(ages_df[["player_id", "season_id", "age"]], on=["player_id", "season_id"])

    if position_group:
        # Would need position info in per90_df or ages_df
        pass

    if metric not in merged.columns:
        raise ValueError(f"Metric '{metric}' not found in data")

    # Group by age and compute mean + confidence interval
    age_curve = merged.groupby("age")[metric].agg(["mean", "std", "count"]).reset_index()
    age_curve.columns = ["age", "mean_value", "std_value", "sample_size"]

    # Filter ages with sufficient sample
    age_curve = age_curve[age_curve["sample_size"] >= 5]

    # Confidence interval (95%)
    age_curve["ci_lower"] = age_curve["mean_value"] - 1.96 * age_curve["std_value"] / np.sqrt(age_curve["sample_size"])
    age_curve["ci_upper"] = age_curve["mean_value"] + 1.96 * age_curve["std_value"] / np.sqrt(age_curve["sample_size"])

    return age_curve


def generate_development_report(profile: DevelopmentProfile) -> str:
    """Generate a text summary of a player's development profile.

    Args:
        profile: Computed DevelopmentProfile.

    Returns:
        Formatted text report.
    """
    lines = [
        f"Development Report: {profile.player_name}",
        f"{'═' * 50}",
        f"Position: {profile.position_group.title()}",
        f"Seasons tracked: {len(profile.seasons)}",
        f"Trajectory: {profile.trajectory.upper()}",
        "",
        "Metric Trends (slope per season):",
        "─" * 40,
    ]

    for metric, slope in sorted(profile.trend_slopes.items(), key=lambda x: x[1], reverse=True):
        direction = "↑" if slope > 0.01 else "↓" if slope < -0.01 else "→"
        lines.append(f"  {direction} {metric}: {slope:+.4f}/season")

    if profile.percentile_changes:
        lines.extend([
            "",
            "Overall Changes (first → last season):",
            "─" * 40,
        ])
        for metric, change in sorted(profile.percentile_changes.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {metric}: {change:+.1f}%")

    if profile.predicted_peak_age:
        lines.extend([
            "",
            f"Expected peak age range: {_PEAK_AGE_RANGES[profile.position_group]}",
        ])

    return "\n".join(lines)
