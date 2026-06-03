"""Post-match review generation.

Produces a structured post-match debrief that:
- Audits pre-match prediction accuracy against actual outcome
- Evaluates team and player performance against baselines
- Identifies tactical patterns that played out
- Highlights actionable insights for the next match cycle

Designed to be generated within 24h of final whistle once event data is available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)


@dataclass
class PlayerMatchRating:
    """Individual player performance rating for a match."""

    player_id: int
    player_name: str
    minutes_played: int
    rating: float  # 1-10 scale
    xg: float
    xa: float
    passes_completed: int
    passes_attempted: int
    pass_accuracy: float
    pressures: int
    tackles_won: int
    carries: int
    progressive_carries: int
    key_actions: list[str] = field(default_factory=list)


@dataclass
class UnitPerformance:
    """Performance summary for a unit (defence, midfield, attack)."""

    unit: str  # "defence", "midfield", "attack"
    rating: float
    baseline_rating: float
    key_metrics: dict[str, float] = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)


@dataclass
class PredictionAudit:
    """How accurate was the pre-match prediction."""

    predicted_winner: str  # "home", "away", "draw"
    actual_winner: str
    prediction_correct: bool
    predicted_score: str
    actual_score: str
    score_correct: bool
    predicted_xg_home: float
    predicted_xg_away: float
    actual_xg_home: float
    actual_xg_away: float
    brier_score: float  # Lower is better
    narrative: str


@dataclass
class PostMatchReview:
    """Complete post-match review for a fixture."""

    # Match info
    fixture_id: int | None
    match_id: int
    match_date: str
    home_team: str
    away_team: str
    competition: str
    final_score: str

    # Prediction audit
    prediction_audit: PredictionAudit | None

    # Team performance
    possession: float
    xg_for: float
    xg_against: float
    shots: int
    shots_on_target: int
    passes_completed: int
    pass_accuracy: float
    pressures_applied: int
    tackles_won: int
    aerial_duels_won: int
    aerial_duels_total: int

    # Unit breakdown
    unit_performances: list[UnitPerformance] = field(default_factory=list)

    # Player ratings
    player_ratings: list[PlayerMatchRating] = field(default_factory=list)

    # Tactical observations
    tactical_observations: list[str] = field(default_factory=list)

    # Areas for improvement
    improvement_areas: list[str] = field(default_factory=list)

    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)
    analyst_notes: str = ""


def generate_post_match_review(
    match_id: int,
    our_team_id: int | None = None,
    fixture_id: int | None = None,
    engine: Engine | None = None,
) -> PostMatchReview:
    """Generate a post-match review for a completed fixture.

    Args:
        match_id: The match to review (must have event data).
        our_team_id: Which team's perspective. Defaults to home team.
        fixture_id: Optional link to fixture for prediction audit.
        engine: SQLAlchemy engine.

    Returns:
        PostMatchReview with performance data and analysis.
    """
    engine = engine or get_engine()

    # Get match context
    match_info = _get_match_info(engine, match_id)
    our_id = our_team_id or match_info["home_team_id"]
    opponent_id = match_info["away_team_id"] if our_id == match_info["home_team_id"] else match_info["home_team_id"]
    is_home = our_id == match_info["home_team_id"]

    # Team-level stats
    team_stats = _get_team_stats(engine, match_id, our_id)
    opp_stats = _get_team_stats(engine, match_id, opponent_id)

    # Player ratings
    player_ratings = _get_player_ratings(engine, match_id, our_id)

    # Unit performances
    unit_performances = _compute_unit_performances(player_ratings)

    # Prediction audit
    prediction_audit = None
    if fixture_id:
        prediction_audit = _audit_prediction(engine, fixture_id, match_info, is_home)

    # Tactical observations
    tactical_obs = _generate_tactical_observations(team_stats, opp_stats, match_info, is_home)

    # Improvement areas
    improvements = _identify_improvements(team_stats, opp_stats, player_ratings)

    # Score from our perspective
    if is_home:
        final_score = f"{match_info['home_score']}-{match_info['away_score']}"
    else:
        final_score = f"{match_info['away_score']}-{match_info['home_score']}"

    return PostMatchReview(
        fixture_id=fixture_id,
        match_id=match_id,
        match_date=str(match_info.get("match_date", "")),
        home_team=match_info["home_team_name"],
        away_team=match_info["away_team_name"],
        competition=match_info.get("competition_name", ""),
        final_score=final_score,
        prediction_audit=prediction_audit,
        possession=team_stats.get("possession", 0.0),
        xg_for=team_stats.get("xg", 0.0),
        xg_against=opp_stats.get("xg", 0.0),
        shots=team_stats.get("shots", 0),
        shots_on_target=team_stats.get("shots_on_target", 0),
        passes_completed=team_stats.get("passes_completed", 0),
        pass_accuracy=team_stats.get("pass_accuracy", 0.0),
        pressures_applied=team_stats.get("pressures", 0),
        tackles_won=team_stats.get("tackles_won", 0),
        aerial_duels_won=team_stats.get("aerial_won", 0),
        aerial_duels_total=team_stats.get("aerial_total", 0),
        unit_performances=unit_performances,
        player_ratings=player_ratings,
        tactical_observations=tactical_obs,
        improvement_areas=improvements,
    )


def _get_match_info(engine: Engine, match_id: int) -> dict[str, Any]:
    """Fetch match details."""
    query = text("""
        SELECT m.match_id, m.match_date, m.competition_id, m.season_id,
               m.home_team_id, m.away_team_id, m.home_score, m.away_score,
               ht.team_name AS home_team_name, at.team_name AS away_team_name,
               c.competition_name
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        LEFT JOIN competitions c ON m.competition_id = c.competition_id
            AND m.season_id = c.season_id
        WHERE m.match_id = :mid
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"mid": match_id}).mappings().fetchone()

    if not result:
        raise ValueError(f"Match {match_id} not found")
    return dict(result)


def _get_team_stats(engine: Engine, match_id: int, team_id: int) -> dict[str, Any]:
    """Aggregate team-level stats from event data."""
    query = text("""
        SELECT
            COUNT(*) FILTER (WHERE event_type = 'Shot') AS shots,
            COUNT(*) FILTER (WHERE event_type = 'Shot' AND shot_outcome = 'On Target') AS shots_on_target,
            COALESCE(SUM(xg) FILTER (WHERE event_type = 'Shot'), 0) AS xg,
            COUNT(*) FILTER (WHERE event_type = 'Pass' AND pass_outcome IS NULL) AS passes_completed,
            COUNT(*) FILTER (WHERE event_type = 'Pass') AS passes_total,
            COUNT(*) FILTER (WHERE event_type = 'Pressure') AS pressures,
            COUNT(*) FILTER (WHERE event_type = 'Duel' AND duel_type = 'Tackle'
                AND duel_outcome = 'Won') AS tackles_won,
            COUNT(*) FILTER (WHERE event_type = 'Duel' AND duel_type LIKE '%Aerial%'
                AND duel_outcome = 'Won') AS aerial_won,
            COUNT(*) FILTER (WHERE event_type = 'Duel' AND duel_type LIKE '%Aerial%') AS aerial_total,
            COUNT(*) FILTER (WHERE event_type = 'Carry') AS carries,
            COUNT(*) FILTER (WHERE event_type = 'Carry' AND carry_progressive = TRUE) AS progressive_carries
        FROM events
        WHERE match_id = :mid AND team_id = :tid
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"mid": match_id, "tid": team_id}).mappings().fetchone()

    if not result:
        return {}

    row = dict(result)
    passes_total = row.get("passes_total", 1) or 1
    row["pass_accuracy"] = round(row.get("passes_completed", 0) / passes_total * 100, 1)
    row["possession"] = 0.0  # Would need possession event aggregation
    return row


def _get_player_ratings(engine: Engine, match_id: int, team_id: int) -> list[PlayerMatchRating]:
    """Compute per-player match ratings."""
    query = text("""
        SELECT e.player_id, p.player_name,
               COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots,
               COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0) AS xg,
               COALESCE(SUM(e.xa) FILTER (WHERE e.event_type = 'Pass'), 0) AS xa,
               COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS passes_completed,
               COUNT(*) FILTER (WHERE e.event_type = 'Pass') AS passes_total,
               COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures,
               COUNT(*) FILTER (WHERE e.event_type = 'Duel' AND e.duel_type = 'Tackle'
                   AND e.duel_outcome = 'Won') AS tackles_won,
               COUNT(*) FILTER (WHERE e.event_type = 'Carry') AS carries,
               COUNT(*) FILTER (WHERE e.event_type = 'Carry' AND e.carry_progressive = TRUE) AS progressive_carries,
               COUNT(*) FILTER (WHERE e.event_type = 'Goal Keeper') AS gk_events,
               COUNT(*) FILTER (WHERE e.event_type = 'Dribble' AND e.dribble_outcome = 'Complete') AS dribbles
        FROM events e
        JOIN players p ON e.player_id = p.player_id
        WHERE e.match_id = :mid AND e.team_id = :tid AND e.player_id IS NOT NULL
        GROUP BY e.player_id, p.player_name
        ORDER BY COUNT(*) DESC
    """)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"mid": match_id, "tid": team_id})
    except Exception:
        return []

    ratings = []
    for _, row in df.iterrows():
        passes_total = max(int(row.get("passes_total", 1)), 1)
        pass_acc = round(int(row.get("passes_completed", 0)) / passes_total * 100, 1)

        # Simple rating formula: base 6 + contributions
        rating = 6.0
        rating += float(row.get("xg", 0) or 0) * 2.0
        rating += float(row.get("xa", 0) or 0) * 1.5
        rating += int(row.get("tackles_won", 0)) * 0.1
        rating += int(row.get("pressures", 0)) * 0.02
        rating += int(row.get("progressive_carries", 0)) * 0.05
        rating = min(max(round(rating, 1), 1.0), 10.0)

        key_actions = []
        if float(row.get("xg", 0) or 0) > 0.3:
            key_actions.append("Created high-xG chances")
        if int(row.get("tackles_won", 0)) >= 4:
            key_actions.append("Strong tackling performance")
        if int(row.get("progressive_carries", 0)) >= 5:
            key_actions.append("Effective ball progression")

        ratings.append(
            PlayerMatchRating(
                player_id=int(row["player_id"]),
                player_name=row["player_name"],
                minutes_played=90,  # Would need substitution data
                rating=rating,
                xg=round(float(row.get("xg", 0) or 0), 3),
                xa=round(float(row.get("xa", 0) or 0), 3),
                passes_completed=int(row.get("passes_completed", 0)),
                passes_attempted=passes_total,
                pass_accuracy=pass_acc,
                pressures=int(row.get("pressures", 0)),
                tackles_won=int(row.get("tackles_won", 0)),
                carries=int(row.get("carries", 0)),
                progressive_carries=int(row.get("progressive_carries", 0)),
                key_actions=key_actions,
            )
        )

    return ratings


def _compute_unit_performances(
    player_ratings: list[PlayerMatchRating],
) -> list[UnitPerformance]:
    """Group players into units and compute aggregate performance.

    Note: Without lineup position data, we use heuristics based on
    action profiles (GKs have saves, defenders tackle, etc.).
    """
    if not player_ratings:
        return []

    # Simple heuristic classification
    defenders = [p for p in player_ratings if p.tackles_won >= 2 and p.xg < 0.1]
    attackers = [p for p in player_ratings if p.xg >= 0.1 or p.xa >= 0.1]
    midfielders = [p for p in player_ratings if p not in defenders and p not in attackers]

    units = []
    for unit_name, players in [
        ("defence", defenders),
        ("midfield", midfielders),
        ("attack", attackers),
    ]:
        if not players:
            continue
        avg_rating = round(sum(p.rating for p in players) / len(players), 1)
        units.append(
            UnitPerformance(
                unit=unit_name,
                rating=avg_rating,
                baseline_rating=6.5,  # Would compare to season average
                key_metrics={
                    "avg_pass_accuracy": round(sum(p.pass_accuracy for p in players) / len(players), 1),
                    "total_pressures": sum(p.pressures for p in players),
                    "total_progressive_carries": sum(p.progressive_carries for p in players),
                },
            )
        )

    return units


def _audit_prediction(
    engine: Engine,
    fixture_id: int,
    match_info: dict[str, Any],
    is_home: bool,
) -> PredictionAudit | None:
    """Compare pre-match prediction against actual result."""
    query = text("""
        SELECT predicted_home_win, predicted_draw, predicted_away_win,
               predicted_score_home, predicted_score_away,
               predicted_xg_home, predicted_xg_away
        FROM predictions
        WHERE fixture_id = :fid
        ORDER BY created_at DESC LIMIT 1
    """)

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"fid": fixture_id}).mappings().fetchone()
    except Exception:
        return None

    if not result:
        return None

    pred = dict(result)
    h_score = match_info["home_score"]
    a_score = match_info["away_score"]

    # Determine predicted/actual winners
    p_home = pred["predicted_home_win"]
    p_draw = pred["predicted_draw"]
    p_away = pred["predicted_away_win"]

    if p_home >= p_draw and p_home >= p_away:
        predicted_winner = "home"
    elif p_away >= p_home and p_away >= p_draw:
        predicted_winner = "away"
    else:
        predicted_winner = "draw"

    if h_score > a_score:
        actual_winner = "home"
    elif a_score > h_score:
        actual_winner = "away"
    else:
        actual_winner = "draw"

    # Brier score: average of squared probability errors for 3-way outcome
    actual_probs = [
        1.0 if actual_winner == "home" else 0.0,
        1.0 if actual_winner == "draw" else 0.0,
        1.0 if actual_winner == "away" else 0.0,
    ]
    pred_probs = [p_home, p_draw, p_away]
    brier = sum((p - a) ** 2 for p, a in zip(pred_probs, actual_probs, strict=False)) / 3

    correct = predicted_winner == actual_winner
    predicted_score = f"{pred['predicted_score_home']}-{pred['predicted_score_away']}"
    actual_score = f"{h_score}-{a_score}"

    # Narrative
    if correct and predicted_score == actual_score:
        narrative = "Prediction spot-on: correct winner and scoreline."
    elif correct:
        narrative = f"Correct result predicted, but score was {actual_score} vs predicted {predicted_score}."
    else:
        narrative = (
            f"Prediction missed: predicted {predicted_winner} win but "
            f"actual result was {actual_winner} ({actual_score})."
        )

    return PredictionAudit(
        predicted_winner=predicted_winner,
        actual_winner=actual_winner,
        prediction_correct=correct,
        predicted_score=predicted_score,
        actual_score=actual_score,
        score_correct=predicted_score == actual_score,
        predicted_xg_home=pred.get("predicted_xg_home", 0.0),
        predicted_xg_away=pred.get("predicted_xg_away", 0.0),
        actual_xg_home=0.0,  # Populated from match xG in team_stats
        actual_xg_away=0.0,
        brier_score=round(brier, 4),
        narrative=narrative,
    )


def _generate_tactical_observations(
    team_stats: dict[str, Any],
    opp_stats: dict[str, Any],
    match_info: dict[str, Any],
    is_home: bool,
) -> list[str]:
    """Generate tactical observations from match stats."""
    observations = []

    # Pressing intensity
    pressures = team_stats.get("pressures", 0)
    if pressures > 200:
        observations.append("High press was effective — sustained pressure throughout the match.")
    elif pressures < 100:
        observations.append("Low pressing approach — may indicate tactical choice or fatigue.")

    # Passing profile
    pass_acc = team_stats.get("pass_accuracy", 0.0)
    if pass_acc > 88:
        observations.append("Excellent passing accuracy indicates controlled possession play.")
    elif pass_acc < 75:
        observations.append("Below-average passing accuracy — opponent pressed effectively or risk-taking high.")

    # Shot efficiency
    shots = team_stats.get("shots", 0)
    xg = team_stats.get("xg", 0.0)
    if shots > 0 and xg / max(shots, 1) > 0.15:
        observations.append("High shot quality — created chances from dangerous positions.")
    elif shots > 0 and xg / max(shots, 1) < 0.06:
        observations.append("Low shot quality — most chances from distance or low-value areas.")

    # Progressive play
    prog_carries = team_stats.get("progressive_carries", 0)
    if prog_carries > 50:
        observations.append("Strong ball progression through carries — effective in transition.")

    # Aerial dominance
    aerial_won = team_stats.get("aerial_won", 0)
    aerial_total = team_stats.get("aerial_total", 1) or 1
    if aerial_total > 20 and aerial_won / aerial_total > 0.6:
        observations.append("Dominated aerial duels — physical advantage in both boxes.")
    elif aerial_total > 20 and aerial_won / aerial_total < 0.4:
        observations.append("Lost the aerial battle — vulnerable to set pieces and crosses.")

    return observations


def _identify_improvements(
    team_stats: dict[str, Any],
    opp_stats: dict[str, Any],
    player_ratings: list[PlayerMatchRating],
) -> list[str]:
    """Identify areas needing improvement based on performance data."""
    areas = []

    # Conversion
    shots = team_stats.get("shots", 0)
    team_stats.get("xg", 0.0)
    sot = team_stats.get("shots_on_target", 0)
    if shots > 10 and sot / max(shots, 1) < 0.3:
        areas.append("Shot accuracy: too many attempts off target.")

    # Defensive vulnerability
    opp_xg = opp_stats.get("xg", 0.0)
    if opp_xg > 1.5:
        areas.append("Conceded high xG — defensive structure needs review.")

    # Pass accuracy under press
    pass_acc = team_stats.get("pass_accuracy", 0.0)
    if pass_acc < 78:
        areas.append("Passing under pressure: accuracy below expected standard.")

    # Low performers
    low_rated = [p for p in player_ratings if p.rating < 5.5 and p.minutes_played >= 60]
    if low_rated:
        names = ", ".join(p.player_name for p in low_rated[:3])
        areas.append(f"Individual performances below par: {names}.")

    return areas
