"""Structured performance reviews and aggregated intelligence.

Provides higher-level review types that aggregate data from multiple
post-match reviews and prediction cycles:
- Player review: season-long or window performance summary
- Unit review: collective analysis of a positional group
- Competition review: campaign progress and trajectory
- Opponent dossier: cumulative opponent intelligence across encounters

These are used for mid-season reports, transfer windows, and board briefings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)


@dataclass
class PlayerReview:
    """Season-long or window performance review for a player."""

    player_id: int
    player_name: str
    position: str
    matches_played: int
    minutes_played: int
    starts: int

    # Outputs
    goals: int
    assists: int
    xg: float
    xa: float
    xg_overperformance: float  # goals - xG

    # On-ball
    passes_per_match: float
    pass_accuracy: float
    progressive_carries_per_match: float
    dribble_success_rate: float
    key_passes_per_match: float

    # Off-ball
    pressures_per_match: float
    tackles_per_match: float
    interceptions_per_match: float

    # Rating
    average_rating: float
    rating_trend: str  # "improving", "stable", "declining"
    best_match_id: int | None = None
    worst_match_id: int | None = None

    # Context
    competition_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    trend_data: list[dict[str, float]] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    development_areas: list[str] = field(default_factory=list)


@dataclass
class UnitReview:
    """Aggregated review of a positional unit across a period."""

    unit: str  # "goalkeeping", "defence", "midfield", "attack"
    period_start: date
    period_end: date
    matches_reviewed: int

    # Aggregate metrics
    average_rating: float
    best_match_rating: float
    worst_match_rating: float

    # Unit-specific KPIs
    kpis: dict[str, float] = field(default_factory=dict)
    kpi_baselines: dict[str, float] = field(default_factory=dict)

    # Player contributions
    player_summaries: list[dict[str, Any]] = field(default_factory=list)

    # Observations
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class CompetitionReview:
    """Campaign progress review for a specific competition."""

    competition_id: int
    competition_name: str
    season_id: int

    # Progress
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    points: int | None  # League only
    position: int | None  # League only

    # Performance
    xg_for: float
    xg_against: float
    xg_difference: float
    points_above_expected: float  # Actual vs xG-predicted points

    # Prediction accuracy
    predictions_made: int
    predictions_correct: int
    average_brier_score: float

    # Form
    last_5_form: str  # "WWDLW"
    form_trajectory: str  # "improving", "stable", "declining"

    # Narrative
    headline: str = ""
    key_themes: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass
class OpponentDossier:
    """Cumulative intelligence file on an opponent across encounters."""

    team_id: int
    team_name: str
    last_updated: date

    # Encounter history
    total_encounters: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int

    # Tactical profile
    preferred_formation: str
    style_tags: list[str]  # ["high-press", "possession", "counter-attacking"]
    tactical_dimensions: dict[str, float] = field(default_factory=dict)

    # Set-piece profile
    set_piece_threat_level: str = "medium"
    set_piece_notes: list[str] = field(default_factory=list)

    # Key personnel
    key_players: list[dict[str, Any]] = field(default_factory=list)
    manager: str = ""
    manager_since: str = ""

    # Insights from past encounters
    what_worked: list[str] = field(default_factory=list)
    what_failed: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def generate_player_review(
    player_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
    season_id: int | None = None,
    engine: Engine | None = None,
) -> PlayerReview:
    """Generate a comprehensive player performance review.

    Args:
        player_id: Player to review.
        from_date: Start of review period.
        to_date: End of review period.
        season_id: Season filter (alternative to date range).
        engine: SQLAlchemy engine.

    Returns:
        PlayerReview with aggregated metrics and analysis.
    """
    engine = engine or get_engine()

    # Get player info
    player_info = _get_player_info(engine, player_id)

    # Aggregated match stats
    stats = _aggregate_player_stats(engine, player_id, from_date, to_date, season_id)

    matches = max(stats.get("matches", 1), 1)
    minutes = stats.get("minutes", 0)
    goals = stats.get("goals", 0)
    xg = stats.get("xg", 0.0)

    # Match-by-match ratings for trend
    match_ratings = _get_match_ratings(engine, player_id, from_date, to_date, season_id)
    avg_rating = sum(r["rating"] for r in match_ratings) / max(len(match_ratings), 1)

    # Determine trend (compare first half vs second half)
    if len(match_ratings) >= 4:
        mid = len(match_ratings) // 2
        first_half_avg = sum(r["rating"] for r in match_ratings[:mid]) / mid
        second_half_avg = sum(r["rating"] for r in match_ratings[mid:]) / (
            len(match_ratings) - mid
        )
        if second_half_avg - first_half_avg > 0.3:
            trend = "improving"
        elif first_half_avg - second_half_avg > 0.3:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "stable"

    # Identify strengths/weaknesses
    strengths, dev_areas = _assess_player_qualities(stats, matches)

    return PlayerReview(
        player_id=player_id,
        player_name=player_info.get("player_name", f"Player {player_id}"),
        position=player_info.get("position", ""),
        matches_played=matches,
        minutes_played=minutes,
        starts=stats.get("starts", 0),
        goals=goals,
        assists=stats.get("assists", 0),
        xg=round(xg, 2),
        xa=round(stats.get("xa", 0.0), 2),
        xg_overperformance=round(goals - xg, 2),
        passes_per_match=round(stats.get("passes", 0) / matches, 1),
        pass_accuracy=round(stats.get("pass_accuracy", 0.0), 1),
        progressive_carries_per_match=round(
            stats.get("progressive_carries", 0) / matches, 1
        ),
        dribble_success_rate=round(stats.get("dribble_success", 0.0), 1),
        key_passes_per_match=round(stats.get("key_passes", 0) / matches, 1),
        pressures_per_match=round(stats.get("pressures", 0) / matches, 1),
        tackles_per_match=round(stats.get("tackles_won", 0) / matches, 1),
        interceptions_per_match=round(stats.get("interceptions", 0) / matches, 1),
        average_rating=round(avg_rating, 1),
        rating_trend=trend,
        best_match_id=match_ratings[0]["match_id"] if match_ratings else None,
        worst_match_id=match_ratings[-1]["match_id"] if match_ratings else None,
        trend_data=match_ratings,
        strengths=strengths,
        development_areas=dev_areas,
    )


def generate_competition_review(
    competition_id: int,
    season_id: int,
    team_id: int,
    engine: Engine | None = None,
) -> CompetitionReview:
    """Generate a competition campaign review.

    Args:
        competition_id: Competition to review.
        season_id: Season.
        team_id: Our team.
        engine: SQLAlchemy engine.

    Returns:
        CompetitionReview with campaign progress.
    """
    engine = engine or get_engine()

    # Get match results
    results = _get_competition_results(engine, competition_id, season_id, team_id)

    matches = len(results)
    wins = sum(1 for r in results if r["result"] == "W")
    draws = sum(1 for r in results if r["result"] == "D")
    losses = sum(1 for r in results if r["result"] == "L")
    gf = sum(r["goals_for"] for r in results)
    ga = sum(r["goals_against"] for r in results)
    xg_for = sum(r.get("xg_for", 0.0) for r in results)
    xg_against = sum(r.get("xg_against", 0.0) for r in results)

    # Points (league only)
    points = wins * 3 + draws

    # Expected points from xG
    # Simple: if xG_for > xG_against → expected win etc.
    expected_points = 0.0
    for r in results:
        xgf = r.get("xg_for", 0.0)
        xga = r.get("xg_against", 0.0)
        if xgf > xga + 0.3:
            expected_points += 3.0
        elif abs(xgf - xga) <= 0.3:
            expected_points += 1.0

    # Prediction accuracy
    pred_stats = _get_prediction_accuracy(engine, competition_id, season_id, team_id)

    # Form
    last_5 = results[-5:] if len(results) >= 5 else results
    form_str = "".join(r["result"] for r in last_5)

    # Trajectory
    if matches >= 6:
        recent = results[-(matches // 3) :]
        early = results[: (matches // 3)]
        recent_ppg = sum(
            3 if r["result"] == "W" else 1 if r["result"] == "D" else 0 for r in recent
        ) / max(len(recent), 1)
        early_ppg = sum(
            3 if r["result"] == "W" else 1 if r["result"] == "D" else 0 for r in early
        ) / max(len(early), 1)
        if recent_ppg - early_ppg > 0.3:
            trajectory = "improving"
        elif early_ppg - recent_ppg > 0.3:
            trajectory = "declining"
        else:
            trajectory = "stable"
    else:
        trajectory = "stable"

    # Competition name
    comp_name = _get_competition_name(engine, competition_id, season_id)

    return CompetitionReview(
        competition_id=competition_id,
        competition_name=comp_name,
        season_id=season_id,
        matches_played=matches,
        wins=wins,
        draws=draws,
        losses=losses,
        goals_for=gf,
        goals_against=ga,
        points=points,
        position=None,  # Would require league table computation
        xg_for=round(xg_for, 2),
        xg_against=round(xg_against, 2),
        xg_difference=round(xg_for - xg_against, 2),
        points_above_expected=round(points - expected_points, 1),
        predictions_made=pred_stats.get("total", 0),
        predictions_correct=pred_stats.get("correct", 0),
        average_brier_score=pred_stats.get("avg_brier", 0.0),
        last_5_form=form_str,
        form_trajectory=trajectory,
    )


def generate_opponent_dossier(
    opponent_id: int,
    our_team_id: int,
    engine: Engine | None = None,
) -> OpponentDossier:
    """Generate a cumulative opponent intelligence dossier.

    Aggregates all data across encounters with this opponent.

    Args:
        opponent_id: Opponent team.
        our_team_id: Our team (for perspective).
        engine: SQLAlchemy engine.

    Returns:
        OpponentDossier with comprehensive opponent profile.
    """
    engine = engine or get_engine()

    # Team name
    opp_name = _get_team_name(engine, opponent_id)

    # Head-to-head record
    h2h = _get_h2h_record(engine, our_team_id, opponent_id)

    # Tactical profile from matchup analysis
    tactical = _get_tactical_profile(engine, opponent_id)

    # Key players
    key_players = _get_opponent_key_players_dossier(engine, opponent_id)

    return OpponentDossier(
        team_id=opponent_id,
        team_name=opp_name,
        last_updated=date.today(),
        total_encounters=h2h.get("total", 0),
        wins=h2h.get("wins", 0),
        draws=h2h.get("draws", 0),
        losses=h2h.get("losses", 0),
        goals_for=h2h.get("goals_for", 0),
        goals_against=h2h.get("goals_against", 0),
        preferred_formation=tactical.get("formation", "Unknown"),
        style_tags=tactical.get("style_tags", []),
        tactical_dimensions=tactical.get("dimensions", {}),
        key_players=key_players,
    )


# ─── Internal Helpers ──────────────────────────────────────────────────────


def _get_player_info(engine: Engine, player_id: int) -> dict[str, Any]:
    """Fetch player basic info."""
    query = text("SELECT player_name, position FROM players WHERE player_id = :pid")
    try:
        with engine.connect() as conn:
            row = conn.execute(query, {"pid": player_id}).mappings().fetchone()
        return dict(row) if row else {}
    except Exception:
        return {}


def _aggregate_player_stats(
    engine: Engine,
    player_id: int,
    from_date: date | None,
    to_date: date | None,
    season_id: int | None,
) -> dict[str, Any]:
    """Aggregate player stats across matches in the period."""
    conditions = ["e.player_id = :pid"]
    params: dict[str, Any] = {"pid": player_id}

    if season_id is not None:
        conditions.append("m.season_id = :sid")
        params["sid"] = season_id
    if from_date is not None:
        conditions.append("m.match_date >= :from_date")
        params["from_date"] = from_date
    if to_date is not None:
        conditions.append("m.match_date <= :to_date")
        params["to_date"] = to_date

    where = " AND ".join(conditions)
    query = text(f"""
        SELECT
            COUNT(DISTINCT e.match_id) AS matches,
            COUNT(*) FILTER (WHERE e.event_type = 'Shot' AND e.shot_outcome = 'Goal') AS goals,
            COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0) AS xg,
            COALESCE(SUM(e.xa) FILTER (WHERE e.event_type = 'Pass'), 0) AS xa,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass') AS passes,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS passes_completed,
            COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures,
            COUNT(*) FILTER (WHERE e.event_type = 'Duel' AND e.duel_type = 'Tackle'
                AND e.duel_outcome = 'Won') AS tackles_won,
            COUNT(*) FILTER (WHERE e.event_type = 'Interception') AS interceptions,
            COUNT(*) FILTER (WHERE e.event_type = 'Carry' AND e.carry_progressive = TRUE) AS progressive_carries,
            COUNT(*) FILTER (WHERE e.event_type = 'Dribble' AND e.dribble_outcome = 'Complete') AS dribbles_complete,
            COUNT(*) FILTER (WHERE e.event_type = 'Dribble') AS dribbles_total,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_goal_assist = TRUE) AS assists,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_shot_assist = TRUE) AS key_passes
        FROM events e
        JOIN matches m ON e.match_id = m.match_id
        WHERE {where}
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(query, params).mappings().fetchone()
        if not result:
            return {}
        row = dict(result)
        passes_total = max(row.get("passes", 1), 1)
        row["pass_accuracy"] = row.get("passes_completed", 0) / passes_total * 100
        dribbles_total = max(row.get("dribbles_total", 1), 1)
        row["dribble_success"] = row.get("dribbles_complete", 0) / dribbles_total * 100
        return row
    except Exception:
        return {}


def _get_match_ratings(
    engine: Engine,
    player_id: int,
    from_date: date | None,
    to_date: date | None,
    season_id: int | None,
) -> list[dict[str, float]]:
    """Get per-match ratings sorted by performance (best first)."""
    conditions = ["e.player_id = :pid"]
    params: dict[str, Any] = {"pid": player_id}

    if season_id is not None:
        conditions.append("m.season_id = :sid")
        params["sid"] = season_id
    if from_date:
        conditions.append("m.match_date >= :from_date")
        params["from_date"] = from_date
    if to_date:
        conditions.append("m.match_date <= :to_date")
        params["to_date"] = to_date

    where = " AND ".join(conditions)
    query = text(f"""
        SELECT e.match_id, m.match_date,
            COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0) AS xg,
            COALESCE(SUM(e.xa) FILTER (WHERE e.event_type = 'Pass'), 0) AS xa,
            COUNT(*) FILTER (WHERE e.event_type = 'Duel' AND e.duel_type = 'Tackle'
                AND e.duel_outcome = 'Won') AS tackles,
            COUNT(*) FILTER (WHERE e.event_type = 'Carry' AND e.carry_progressive = TRUE) AS prog_carries
        FROM events e
        JOIN matches m ON e.match_id = m.match_id
        WHERE {where}
        GROUP BY e.match_id, m.match_date
        ORDER BY m.match_date ASC
    """)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)
    except Exception:
        return []

    ratings = []
    for _, row in df.iterrows():
        rating = 6.0
        rating += float(row.get("xg", 0)) * 2.0
        rating += float(row.get("xa", 0)) * 1.5
        rating += int(row.get("tackles", 0)) * 0.1
        rating += int(row.get("prog_carries", 0)) * 0.05
        rating = min(max(round(rating, 1), 1.0), 10.0)
        ratings.append(
            {
                "match_id": int(row["match_id"]),
                "match_date": str(row["match_date"]),
                "rating": rating,
            }
        )

    return sorted(ratings, key=lambda x: x["rating"], reverse=True)


def _assess_player_qualities(
    stats: dict[str, Any], matches: int
) -> tuple[list[str], list[str]]:
    """Identify player strengths and development areas."""
    strengths = []
    dev_areas = []

    # Goal threat
    xg_per_match = stats.get("xg", 0.0) / matches
    if xg_per_match > 0.3:
        strengths.append("High-volume goal threat")
    elif xg_per_match < 0.05 and stats.get("goals", 0) > 0:
        strengths.append("Clinical finisher — overperforms xG")

    # Creative
    xa_per_match = stats.get("xa", 0.0) / matches
    if xa_per_match > 0.2:
        strengths.append("Elite creative output")

    # Passing
    pass_acc = stats.get("pass_accuracy", 0.0)
    if pass_acc > 90:
        strengths.append("Excellent passer — rarely gives the ball away")
    elif pass_acc < 75:
        dev_areas.append("Passing accuracy below standard")

    # Pressing
    pressures_per_match = stats.get("pressures", 0) / matches
    if pressures_per_match > 20:
        strengths.append("Intense presser — contributes strongly without the ball")
    elif pressures_per_match < 8:
        dev_areas.append("Low pressing contribution — off-ball work rate")

    # Progressive play
    prog_per_match = stats.get("progressive_carries", 0) / matches
    if prog_per_match > 5:
        strengths.append("Effective ball carrier in transition")

    # Dribbling
    dribble_rate = stats.get("dribble_success", 0.0)
    if dribble_rate > 70:
        strengths.append("Reliable dribbler — retains the ball in tight spaces")
    elif dribble_rate < 40 and stats.get("dribbles_total", 0) > 10:
        dev_areas.append("Dribble success rate too low — high turnover risk")

    return strengths, dev_areas


def _get_competition_results(
    engine: Engine, competition_id: int, season_id: int, team_id: int
) -> list[dict[str, Any]]:
    """Get all match results in a competition season."""
    query = text("""
        SELECT m.match_id, m.match_date, m.home_team_id, m.away_team_id,
               m.home_score, m.away_score,
               COALESCE(SUM(e.xg) FILTER (WHERE e.team_id = :tid AND e.event_type = 'Shot'), 0) AS xg_for,
               COALESCE(SUM(e.xg) FILTER (WHERE e.team_id != :tid AND e.event_type = 'Shot'), 0) AS xg_against
        FROM matches m
        LEFT JOIN events e ON e.match_id = m.match_id
        WHERE m.competition_id = :cid AND m.season_id = :sid
            AND (m.home_team_id = :tid OR m.away_team_id = :tid)
        GROUP BY m.match_id, m.match_date, m.home_team_id, m.away_team_id,
                 m.home_score, m.away_score
        ORDER BY m.match_date ASC
    """)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(
                query,
                conn,
                params={"cid": competition_id, "sid": season_id, "tid": team_id},
            )
    except Exception:
        return []

    results = []
    for _, row in df.iterrows():
        is_home = row["home_team_id"] == team_id
        gf = row["home_score"] if is_home else row["away_score"]
        ga = row["away_score"] if is_home else row["home_score"]
        result = "W" if gf > ga else ("D" if gf == ga else "L")
        results.append(
            {
                "match_id": int(row["match_id"]),
                "match_date": str(row["match_date"]),
                "result": result,
                "goals_for": int(gf),
                "goals_against": int(ga),
                "xg_for": float(row.get("xg_for", 0)),
                "xg_against": float(row.get("xg_against", 0)),
            }
        )
    return results


def _get_prediction_accuracy(
    engine: Engine, competition_id: int, season_id: int, team_id: int
) -> dict[str, Any]:
    """Get prediction accuracy stats for a competition."""
    query = text("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE prediction_correct = TRUE) AS correct,
               COALESCE(AVG(brier_score), 0) AS avg_brier
        FROM predictions p
        JOIN fixtures f ON p.fixture_id = f.fixture_id
        WHERE f.competition_id = :cid AND f.season_id = :sid
            AND (f.home_team_id = :tid OR f.away_team_id = :tid)
            AND p.prediction_correct IS NOT NULL
    """)

    try:
        with engine.connect() as conn:
            result = (
                conn.execute(
                    query, {"cid": competition_id, "sid": season_id, "tid": team_id}
                )
                .mappings()
                .fetchone()
            )
        return dict(result) if result else {"total": 0, "correct": 0, "avg_brier": 0.0}
    except Exception:
        return {"total": 0, "correct": 0, "avg_brier": 0.0}


def _get_competition_name(engine: Engine, competition_id: int, season_id: int) -> str:
    """Fetch competition name."""
    query = text("""
        SELECT competition_name FROM competitions
        WHERE competition_id = :cid AND season_id = :sid LIMIT 1
    """)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                query, {"cid": competition_id, "sid": season_id}
            ).fetchone()
        return result[0] if result else f"Competition {competition_id}"
    except Exception:
        return f"Competition {competition_id}"


def _get_team_name(engine: Engine, team_id: int) -> str:
    """Fetch team name."""
    query = text("SELECT team_name FROM teams WHERE team_id = :tid")
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"tid": team_id}).fetchone()
        return result[0] if result else f"Team {team_id}"
    except Exception:
        return f"Team {team_id}"


def _get_h2h_record(engine: Engine, our_id: int, opp_id: int) -> dict[str, Any]:
    """Get head-to-head record."""
    query = text("""
        SELECT m.home_team_id, m.home_score, m.away_score
        FROM matches m
        WHERE (m.home_team_id = :our AND m.away_team_id = :opp)
           OR (m.home_team_id = :opp AND m.away_team_id = :our)
        ORDER BY m.match_date ASC
    """)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"our": our_id, "opp": opp_id})
    except Exception:
        return {
            "total": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
        }

    wins = draws = losses = gf = ga = 0
    for _, row in df.iterrows():
        is_home = row["home_team_id"] == our_id
        our_goals = row["home_score"] if is_home else row["away_score"]
        their_goals = row["away_score"] if is_home else row["home_score"]
        gf += our_goals
        ga += their_goals
        if our_goals > their_goals:
            wins += 1
        elif our_goals == their_goals:
            draws += 1
        else:
            losses += 1

    return {
        "total": len(df),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": gf,
        "goals_against": ga,
    }


def _get_tactical_profile(engine: Engine, team_id: int) -> dict[str, Any]:
    """Get tactical profile from team_ratings or events."""
    # Use latest rating dimensions if available
    query = text("""
        SELECT metadata FROM team_ratings
        WHERE team_id = :tid
        ORDER BY computed_at DESC LIMIT 1
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"tid": team_id}).fetchone()
        if result and result[0]:
            return result[0]  # JSONB column
    except Exception:
        pass

    return {"formation": "Unknown", "style_tags": [], "dimensions": {}}


def _get_opponent_key_players_dossier(
    engine: Engine, team_id: int
) -> list[dict[str, Any]]:
    """Get opponent's most impactful players across all data."""
    query = text("""
        SELECT p.player_id, p.player_name,
               COUNT(DISTINCT e.match_id) AS matches,
               COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0) AS total_xg,
               COALESCE(SUM(e.xa) FILTER (WHERE e.event_type = 'Pass'), 0) AS total_xa,
               COUNT(*) FILTER (WHERE e.event_type = 'Shot' AND e.shot_outcome = 'Goal') AS goals
        FROM events e
        JOIN players p ON e.player_id = p.player_id
        WHERE e.team_id = :tid AND e.player_id IS NOT NULL
        GROUP BY p.player_id, p.player_name
        HAVING COUNT(DISTINCT e.match_id) >= 2
        ORDER BY COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0) +
                 COALESCE(SUM(e.xa) FILTER (WHERE e.event_type = 'Pass'), 0) DESC
        LIMIT 8
    """)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"tid": team_id})
    except Exception:
        return []

    return [
        {
            "player_id": int(row["player_id"]),
            "player_name": row["player_name"],
            "matches": int(row["matches"]),
            "goals": int(row["goals"]),
            "total_xg": round(float(row["total_xg"]), 2),
            "total_xa": round(float(row["total_xa"]), 2),
        }
        for _, row in df.iterrows()
    ]
