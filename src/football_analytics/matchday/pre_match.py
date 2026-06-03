"""Pre-match intelligence pack generation.

Produces a comprehensive pre-match briefing for coaching staff by combining:
- Opponent profile (attack patterns, defensive shape, key threats)
- Match prediction (probabilities, expected scoreline, confidence)
- Tactical matchup analysis (advantages, vulnerabilities, key battles)
- Set-piece intelligence
- Recent form context for both teams

Designed to be generated 48-72h before kick-off and distributed to coaches
and performance analysts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)


@dataclass
class FormRecord:
    """Single match result in recent form."""

    match_date: date
    opponent: str
    result: str  # "W", "D", "L"
    score: str  # "2-1"
    xg_for: float
    xg_against: float
    competition: str


@dataclass
class KeyPlayerThreat:
    """An opponent's dangerous player."""

    player_name: str
    position: str
    xg_per_match: float
    xa_per_match: float
    key_passes_per_match: float
    threat_description: str


@dataclass
class SetPieceIntel:
    """Set-piece intelligence for the opponent."""

    corners_per_match: float
    free_kicks_per_match: float
    set_piece_xg_per_match: float
    preferred_delivery: str  # "inswinging", "outswinging", "short"
    aerial_threat_level: str  # "high", "medium", "low"


@dataclass
class PreMatchPack:
    """Complete pre-match intelligence pack for a fixture."""

    # Fixture info
    fixture_id: int | None
    match_date: date | None
    home_team: str
    away_team: str
    competition: str
    stage: str
    venue_type: str

    # Prediction
    win_probability: float
    draw_probability: float
    loss_probability: float
    expected_score: str
    prediction_confidence: str
    predicted_xg_for: float
    predicted_xg_against: float

    # Opponent profile
    opponent_attack_patterns: list[dict[str, Any]]
    opponent_defensive_shape: list[dict[str, Any]]
    opponent_key_players: list[KeyPlayerThreat]

    # Tactical matchup
    tactical_advantages: list[dict[str, Any]]
    tactical_vulnerabilities: list[str]
    key_battles: list[dict[str, Any]]
    tactical_recommendations: list[str]

    # Set pieces
    set_piece_intel: SetPieceIntel | None = None

    # Form
    our_recent_form: list[FormRecord] = field(default_factory=list)
    opponent_recent_form: list[FormRecord] = field(default_factory=list)

    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)
    analyst_notes: str = ""


def generate_pre_match_pack(
    fixture_id: int | None = None,
    home_team_id: int | None = None,
    away_team_id: int | None = None,
    our_team_id: int | None = None,
    competition_id: int | None = None,
    season_id: int | None = None,
    engine: Engine | None = None,
) -> PreMatchPack:
    """Generate a complete pre-match intelligence pack.

    Can be called with a fixture_id (looks up teams from fixtures table)
    or with explicit team IDs.

    Args:
        fixture_id: Fixture from the calendar (preferred).
        home_team_id: Home team (if not using fixture_id).
        away_team_id: Away team (if not using fixture_id).
        our_team_id: Which team we are (for perspective). Defaults to home.
        competition_id: Competition context for analysis.
        season_id: Season context for analysis.
        engine: SQLAlchemy engine.

    Returns:
        PreMatchPack with all sections populated.
    """
    engine = engine or get_engine()

    # Resolve fixture details
    fixture_info = _resolve_fixture(
        engine, fixture_id, home_team_id, away_team_id, competition_id, season_id
    )
    h_id = fixture_info["home_team_id"]
    a_id = fixture_info["away_team_id"]
    our_id = our_team_id or h_id
    opponent_id = a_id if our_id == h_id else h_id
    comp_id = fixture_info.get("competition_id")
    szn_id = fixture_info.get("season_id")

    # 1. Match prediction
    prediction = _get_prediction(
        engine, h_id, a_id, comp_id, fixture_info["venue_type"]
    )

    # 2. Opponent profile
    attack_patterns = _get_attack_patterns(engine, opponent_id, szn_id)
    defensive_shape = _get_defensive_shape(engine, opponent_id, szn_id)
    key_players = _get_key_players(engine, opponent_id, szn_id)

    # 3. Tactical matchup
    matchup = _get_tactical_matchup(engine, our_id, opponent_id, comp_id, szn_id)

    # 4. Set-piece intelligence
    set_piece_intel = _get_set_piece_intel(engine, opponent_id, szn_id)

    # 5. Recent form
    our_form = _get_recent_form(engine, our_id, szn_id)
    opponent_form = _get_recent_form(engine, opponent_id, szn_id)

    # Determine perspective
    is_home = our_id == h_id
    win_prob = prediction["home_win"] if is_home else prediction["away_win"]
    loss_prob = prediction["away_win"] if is_home else prediction["home_win"]

    # Identify vulnerabilities (dimensions where opponent has advantage)
    vulnerabilities = []
    for dim in matchup.get("dimensions", []):
        if (is_home and dim.get("advantage", 0) < -0.2) or (
            not is_home and dim.get("advantage", 0) > 0.2
        ):
            vulnerabilities.append(dim.get("description", ""))

    return PreMatchPack(
        fixture_id=fixture_id,
        match_date=fixture_info.get("match_date"),
        home_team=fixture_info["home_team_name"],
        away_team=fixture_info["away_team_name"],
        competition=fixture_info.get("competition_name", ""),
        stage=fixture_info.get("stage", ""),
        venue_type=fixture_info["venue_type"],
        win_probability=win_prob,
        draw_probability=prediction["draw"],
        loss_probability=loss_prob,
        expected_score=prediction["most_likely_score"],
        prediction_confidence=prediction["confidence"],
        predicted_xg_for=prediction["xg_home"] if is_home else prediction["xg_away"],
        predicted_xg_against=(
            prediction["xg_away"] if is_home else prediction["xg_home"]
        ),
        opponent_attack_patterns=attack_patterns,
        opponent_defensive_shape=defensive_shape,
        opponent_key_players=key_players,
        tactical_advantages=[
            d
            for d in matchup.get("dimensions", [])
            if (is_home and d.get("advantage", 0) > 0.15)
            or (not is_home and d.get("advantage", 0) < -0.15)
        ],
        tactical_vulnerabilities=vulnerabilities,
        key_battles=matchup.get("key_battles", []),
        tactical_recommendations=matchup.get("recommendations", []),
        set_piece_intel=set_piece_intel,
        our_recent_form=our_form,
        opponent_recent_form=opponent_form,
    )


def _resolve_fixture(
    engine: Engine,
    fixture_id: int | None,
    home_team_id: int | None,
    away_team_id: int | None,
    competition_id: int | None,
    season_id: int | None,
) -> dict[str, Any]:
    """Resolve fixture details from fixture_id or explicit params."""
    if fixture_id is not None:
        query = text("""
            SELECT f.fixture_id, f.competition_id, c.competition_name,
                   f.season_id, f.match_date, f.home_team_id, f.away_team_id,
                   ht.team_name AS home_team_name, at.team_name AS away_team_name,
                   f.venue_type, f.stage
            FROM fixtures f
            JOIN teams ht ON f.home_team_id = ht.team_id
            JOIN teams at ON f.away_team_id = at.team_id
            LEFT JOIN competitions c ON f.competition_id = c.competition_id
                AND f.season_id = c.season_id
            WHERE f.fixture_id = :fid
        """)
        with engine.connect() as conn:
            result = conn.execute(query, {"fid": fixture_id}).mappings().fetchone()
        if result:
            return dict(result)

    # Fallback: construct from explicit params
    home_name = _get_team_name(engine, home_team_id) if home_team_id else "Home"
    away_name = _get_team_name(engine, away_team_id) if away_team_id else "Away"

    return {
        "fixture_id": fixture_id,
        "competition_id": competition_id,
        "competition_name": "",
        "season_id": season_id,
        "match_date": None,
        "home_team_id": home_team_id or 0,
        "away_team_id": away_team_id or 0,
        "home_team_name": home_name,
        "away_team_name": away_name,
        "venue_type": "home",
        "stage": "",
    }


def _get_prediction(
    engine: Engine,
    home_id: int,
    away_id: int,
    competition_id: int | None,
    venue_type: str,
) -> dict[str, Any]:
    """Get match prediction from the prediction engine."""
    try:
        from football_analytics.prediction.match_predictor import (
            MatchPredictor,
            VenueType,
        )

        venue = (
            VenueType(venue_type)
            if venue_type in ("home", "away", "neutral")
            else VenueType.HOME
        )
        predictor = MatchPredictor(engine=engine)
        prediction = predictor.predict(
            team_a_id=home_id,
            team_b_id=away_id,
            competition_id=competition_id,
            venue_type=venue,
        )
        return {
            "home_win": prediction.team_a_win_prob,
            "draw": prediction.draw_prob,
            "away_win": prediction.team_b_win_prob,
            "most_likely_score": f"{prediction.most_likely_score[0]}-{prediction.most_likely_score[1]}",
            "confidence": prediction.confidence,
            "xg_home": prediction.team_a_expected_xg,
            "xg_away": prediction.team_b_expected_xg,
        }
    except Exception as exc:
        logger.warning(f"Prediction engine unavailable: {exc}")
        return {
            "home_win": 0.0,
            "draw": 0.0,
            "away_win": 0.0,
            "most_likely_score": "0-0",
            "confidence": "insufficient",
            "xg_home": 0.0,
            "xg_away": 0.0,
        }


def _get_attack_patterns(
    engine: Engine, team_id: int, season_id: int | None
) -> list[dict[str, Any]]:
    """Get opponent attack pattern breakdown."""
    try:
        from football_analytics.analysis.opponent_profile import (
            get_opponent_attack_patterns,
        )

        if season_id is None:
            return []
        df = get_opponent_attack_patterns(engine, team_id, season_id)
        if df.empty:
            return []
        return df.to_dict(orient="records")
    except Exception:
        return []


def _get_defensive_shape(
    engine: Engine, team_id: int, season_id: int | None
) -> list[dict[str, Any]]:
    """Get opponent defensive shape analysis."""
    try:
        from football_analytics.analysis.opponent_profile import (
            get_opponent_defensive_shape,
        )

        if season_id is None:
            return []
        df = get_opponent_defensive_shape(engine, team_id, season_id)
        if df.empty:
            return []
        return df.to_dict(orient="records")
    except Exception:
        return []


def _get_key_players(
    engine: Engine, team_id: int, season_id: int | None
) -> list[KeyPlayerThreat]:
    """Get opponent key player threats."""
    try:
        from football_analytics.analysis.opponent_profile import (
            get_opponent_key_players,
        )

        if season_id is None:
            return []
        df = get_opponent_key_players(engine, team_id, season_id, top_n=5)
        if df.empty:
            return []

        threats = []
        for _, row in df.iterrows():
            matches = max(int(row.get("matches", 1)), 1)
            threats.append(
                KeyPlayerThreat(
                    player_name=row.get("player_name", "Unknown"),
                    position="",  # Position not in current query
                    xg_per_match=round(float(row.get("total_xg", 0) or 0) / matches, 3),
                    xa_per_match=round(float(row.get("total_xa", 0) or 0) / matches, 3),
                    key_passes_per_match=round(
                        int(row.get("key_passes", 0)) / matches, 1
                    ),
                    threat_description=_describe_player_threat(row),
                )
            )
        return threats
    except Exception:
        return []


def _get_tactical_matchup(
    engine: Engine,
    our_team_id: int,
    opponent_id: int,
    competition_id: int | None,
    season_id: int | None,
) -> dict[str, Any]:
    """Get tactical matchup analysis."""
    try:
        from football_analytics.prediction.tactical_matchup import analyse_matchup

        matchup = analyse_matchup(
            team_a_id=our_team_id,
            team_b_id=opponent_id,
            competition_id=competition_id,
            season_id=season_id,
            engine=engine,
        )
        return {
            "dimensions": [
                {
                    "name": d.name,
                    "team_a_score": d.team_a_score,
                    "team_b_score": d.team_b_score,
                    "advantage": d.advantage,
                    "description": d.description,
                }
                for d in matchup.dimensions
            ],
            "key_battles": [
                {
                    "area": b.area,
                    "team_a_factor": b.team_a_factor,
                    "team_b_factor": b.team_b_factor,
                    "significance": b.significance,
                    "narrative": b.narrative,
                }
                for b in matchup.key_battles
            ],
            "recommendations": matchup.recommendations,
            "overall_advantage": matchup.overall_advantage,
        }
    except Exception as exc:
        logger.warning(f"Tactical matchup unavailable: {exc}")
        return {"dimensions": [], "key_battles": [], "recommendations": []}


def _get_set_piece_intel(
    engine: Engine, team_id: int, season_id: int | None
) -> SetPieceIntel | None:
    """Get set-piece intelligence for opponent."""
    if season_id is None:
        return None

    query = text("""
        SELECT
            COUNT(*) FILTER (WHERE e.play_pattern = 'From Corner') AS corners,
            COUNT(*) FILTER (WHERE e.play_pattern = 'From Free Kick') AS free_kicks,
            COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot' AND
                e.play_pattern IN ('From Corner', 'From Free Kick')), 0) AS sp_xg,
            COUNT(DISTINCT e.match_id) AS matches,
            COUNT(*) FILTER (WHERE e.event_type = 'Duel' AND
                e.duel_type LIKE '%Aerial%' AND e.duel_outcome = 'Won') AS aerial_wins,
            COUNT(*) FILTER (WHERE e.event_type = 'Duel' AND
                e.duel_type LIKE '%Aerial%') AS aerial_total
        FROM events e
        JOIN matches m ON e.match_id = m.match_id
        WHERE e.team_id = :team_id AND m.season_id = :season_id
    """)

    try:
        with engine.connect() as conn:
            result = (
                conn.execute(query, {"team_id": team_id, "season_id": season_id})
                .mappings()
                .fetchone()
            )

        if not result or result["matches"] == 0:
            return None

        matches = result["matches"]
        aerial_rate = result["aerial_wins"] / max(result["aerial_total"], 1)
        aerial_level = (
            "high"
            if aerial_rate > 0.55
            else ("medium" if aerial_rate > 0.45 else "low")
        )

        return SetPieceIntel(
            corners_per_match=round(result["corners"] / matches, 1),
            free_kicks_per_match=round(result["free_kicks"] / matches, 1),
            set_piece_xg_per_match=round(float(result["sp_xg"]) / matches, 3),
            preferred_delivery="inswinging",  # Would require deeper analysis
            aerial_threat_level=aerial_level,
        )
    except Exception:
        return None


def _get_recent_form(
    engine: Engine, team_id: int, season_id: int | None, n_matches: int = 5
) -> list[FormRecord]:
    """Get recent match results for a team."""
    query = text("""
        SELECT m.match_id, m.match_date, m.home_team_id, m.away_team_id,
               m.home_score, m.away_score,
               ht.team_name AS home_name, at.team_name AS away_name,
               c.competition_name,
               COALESCE(SUM(e.xg) FILTER (WHERE e.team_id = :team_id AND e.event_type = 'Shot'), 0) AS xg_for,
               COALESCE(SUM(e.xg) FILTER (WHERE e.team_id != :team_id AND e.event_type = 'Shot'), 0) AS xg_against
        FROM matches m
        JOIN teams ht ON m.home_team_id = ht.team_id
        JOIN teams at ON m.away_team_id = at.team_id
        LEFT JOIN competitions c ON m.competition_id = c.competition_id AND m.season_id = c.season_id
        LEFT JOIN events e ON e.match_id = m.match_id
        WHERE (m.home_team_id = :team_id OR m.away_team_id = :team_id)
        GROUP BY m.match_id, m.match_date, m.home_team_id, m.away_team_id,
                 m.home_score, m.away_score, ht.team_name, at.team_name, c.competition_name
        ORDER BY m.match_date DESC
        LIMIT :n
    """)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"team_id": team_id, "n": n_matches})

        records = []
        for _, row in df.iterrows():
            is_home = row["home_team_id"] == team_id
            goals_for = row["home_score"] if is_home else row["away_score"]
            goals_against = row["away_score"] if is_home else row["home_score"]
            opponent = row["away_name"] if is_home else row["home_name"]

            if goals_for > goals_against:
                result = "W"
            elif goals_for == goals_against:
                result = "D"
            else:
                result = "L"

            records.append(
                FormRecord(
                    match_date=pd.to_datetime(row["match_date"]).date(),
                    opponent=opponent,
                    result=result,
                    score=f"{goals_for}-{goals_against}",
                    xg_for=round(float(row["xg_for"]), 2),
                    xg_against=round(float(row["xg_against"]), 2),
                    competition=row.get("competition_name") or "",
                )
            )
        return records
    except Exception:
        return []


def _get_team_name(engine: Engine, team_id: int) -> str:
    """Fetch team name from database."""
    query = text("SELECT team_name FROM teams WHERE team_id = :tid")
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"tid": team_id}).fetchone()
        return result[0] if result else f"Team {team_id}"
    except Exception:
        return f"Team {team_id}"


def _describe_player_threat(row: pd.Series) -> str:
    """Generate a brief threat description for a key player."""
    xg = float(row.get("total_xg", 0) or 0)
    xa = float(row.get("total_xa", 0) or 0)
    dribbles = int(row.get("dribbles", 0))

    if xg > xa * 2:
        return "Primary goal threat — direct and dangerous in the box"
    elif xa > xg * 2:
        return "Creative playmaker — generates chances for teammates"
    elif dribbles > 3:
        return "Carries the ball effectively — hard to dispossess"
    else:
        return "Balanced attacking threat — contributes goals and assists"
