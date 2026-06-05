"""Analysis endpoints — xG prediction, player profiles, team analysis."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["analysis"])
logger = logging.getLogger(__name__)


# ─── Request/Response Models ────────────────────────────────────────────────


class ShotInput(BaseModel):
    """Input for xG prediction."""

    location_x: float = Field(..., ge=0, le=120, description="X coordinate (StatsBomb pitch)")
    location_y: float = Field(..., ge=0, le=80, description="Y coordinate (StatsBomb pitch)")
    shot_body_part: str = Field("Foot", description="Body part: Foot, Head, Other")
    under_pressure: bool = Field(False, description="Whether shot was under pressure")
    play_pattern: str = Field("From Open Play", description="Play pattern")
    shot_type: str | None = Field(None, description="Shot type: Penalty, Free Kick, etc.")


class XGPredictionResponse(BaseModel):
    xg: float
    distance_to_goal: float
    goal_angle: float
    features_used: dict[str, float]


class SimulationRequest(BaseModel):
    home_xg: float = Field(..., gt=0, le=10, description="Home team expected goals")
    away_xg: float = Field(..., gt=0, le=10, description="Away team expected goals")
    home_team: str = Field("Home", description="Home team name")
    away_team: str = Field("Away", description="Away team name")
    n_simulations: int = Field(10000, ge=100, le=100000)
    home_advantage_factor: float = Field(1.0, ge=0.5, le=2.0)


class SimulationResponse(BaseModel):
    home_team: str
    away_team: str
    n_simulations: int
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    expected_home_goals: float
    expected_away_goals: float
    most_likely_score: list[int]
    over_1_5_prob: float
    over_2_5_prob: float
    over_3_5_prob: float
    btts_prob: float
    top_scorelines: dict[str, float]


class PlayerProfileResponse(BaseModel):
    player_id: int
    player_name: str
    team_name: str | None = None
    season_id: int | None = None
    appearances: int
    goals: int
    total_xg: float
    total_xa: float
    key_passes: int
    passes_completed: int
    passes_attempted: int
    pass_accuracy: float
    pressures: int
    tackles: int
    interceptions: int


class SimilarPlayerResponse(BaseModel):
    player_id: int
    player_name: str
    similarity_score: float
    position: str | None = None


class DevelopmentResponse(BaseModel):
    player_id: int
    player_name: str
    trajectory: str
    seasons_tracked: int
    trend_slopes: dict[str, float]
    percentile_changes: dict[str, float]


class TeamSetPieceResponse(BaseModel):
    team_id: int
    total_set_pieces: int
    corner_count: int | None = None
    corner_goal_rate: float | None = None
    free_kick_count: int | None = None
    free_kick_goal_rate: float | None = None
    xg_from_set_pieces: float | None = None


class PossessionChainSummary(BaseModel):
    team_id: int
    total_chains: int
    avg_chain_length_events: float
    avg_passes_per_chain: float
    final_third_entry_rate: float
    box_entry_rate: float
    dangerous_possession_rate: float
    xg_per_chain: float
    style_distribution: dict[str, float]


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/xg/predict", response_model=XGPredictionResponse)
async def predict_xg(shot: ShotInput) -> XGPredictionResponse:
    """Predict expected goals (xG) for a single shot."""
    import numpy as np
    import pandas as pd

    from football_analytics.analysis.xg_model import (
        engineer_features,
        get_feature_columns,
    )

    shot_df = pd.DataFrame(
        [
            {
                "location_x": shot.location_x,
                "location_y": shot.location_y,
                "shot_body_part": shot.shot_body_part,
                "under_pressure": shot.under_pressure,
                "play_pattern": shot.play_pattern,
                "shot_type": shot.shot_type,
            }
        ]
    )

    features_df = engineer_features(shot_df)
    feature_cols = get_feature_columns()
    feature_values = features_df[feature_cols].iloc[0].to_dict()

    distance = float(features_df["distance_to_goal"].iloc[0])
    angle = float(features_df["goal_angle"].iloc[0])

    # Analytical xG approximation (empirical logistic curve)
    log_odds = 1.1 - 0.08 * distance + 2.5 * angle
    if shot.shot_body_part == "Head":
        log_odds -= 0.5
    if shot.under_pressure:
        log_odds -= 0.3
    if shot.shot_type == "Penalty":
        log_odds = 2.5  # ~0.76 xG

    xg = 1.0 / (1.0 + np.exp(-log_odds))

    return XGPredictionResponse(
        xg=round(float(xg), 4),
        distance_to_goal=round(distance, 2),
        goal_angle=round(angle, 4),
        features_used={k: round(float(v), 4) for k, v in feature_values.items()},
    )


@router.post("/simulation/match-direct", response_model=SimulationResponse)
async def simulate_match_endpoint(request: Request, sim_req: SimulationRequest) -> SimulationResponse:
    """Simulate a match outcome using Monte Carlo methods.

    Accepts raw xG values directly.
    """
    from football_analytics.analysis.simulation import simulate_match

    result = simulate_match(
        home_xg=sim_req.home_xg,
        away_xg=sim_req.away_xg,
        home_team=sim_req.home_team,
        away_team=sim_req.away_team,
        n_simulations=sim_req.n_simulations,
        home_advantage_factor=sim_req.home_advantage_factor,
    )

    top_scores = sorted(result.scoreline_probabilities.items(), key=lambda x: x[1], reverse=True)[:10]
    score_dict = {f"{h}-{a}": prob for (h, a), prob in top_scores}

    return SimulationResponse(
        home_team=result.home_team,
        away_team=result.away_team,
        n_simulations=result.n_simulations,
        home_win_prob=result.home_win_prob,
        draw_prob=result.draw_prob,
        away_win_prob=result.away_win_prob,
        expected_home_goals=result.expected_home_goals,
        expected_away_goals=result.expected_away_goals,
        most_likely_score=list(result.most_likely_score),
        over_1_5_prob=result.over_1_5_prob,
        over_2_5_prob=result.over_2_5_prob,
        over_3_5_prob=result.over_3_5_prob,
        btts_prob=result.btts_prob,
        top_scorelines=score_dict,
    )


@router.get("/players/{player_id}/profile", response_model=PlayerProfileResponse)
async def get_player_profile(
    player_id: int,
    season_id: int | None = Query(None, description="Filter by season"),
) -> PlayerProfileResponse:
    """Get player performance profile."""
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()

    query = """
        SELECT player_id, player_name, team_name, season_id,
               appearances, goals, total_xg, total_xa, key_passes,
               passes_completed, passes_attempted, pressures, tackles, interceptions
        FROM mv_player_season_stats
        WHERE player_id = :player_id
    """
    params: dict[str, Any] = {"player_id": player_id}

    if season_id:
        query += " AND season_id = :season_id"
        params["season_id"] = season_id

    with engine.connect() as conn:
        result = conn.execute(text(query), params).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    return PlayerProfileResponse(
        player_id=result.player_id,
        player_name=result.player_name,
        team_name=result.team_name,
        season_id=result.season_id,
        appearances=result.appearances,
        goals=result.goals,
        total_xg=float(result.total_xg),
        total_xa=float(result.total_xa),
        key_passes=result.key_passes,
        passes_completed=result.passes_completed,
        passes_attempted=result.passes_attempted,
        pass_accuracy=round(result.passes_completed / max(result.passes_attempted, 1), 3),
        pressures=result.pressures,
        tackles=result.tackles,
        interceptions=result.interceptions,
    )


@router.get("/players/{player_id}/similar", response_model=list[SimilarPlayerResponse])
async def get_similar_players(
    player_id: int,
    season_id: int = Query(106, description="Season to compute vectors from"),
    top_n: int = Query(10, ge=1, le=50, description="Number of similar players"),
) -> list[SimilarPlayerResponse]:
    """Find players with similar statistical profiles."""
    from football_analytics.analysis.similarity import (
        compute_player_vectors,
        find_similar_players,
    )
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()

    try:
        vectors = compute_player_vectors(season_id, engine, min_appearances=3)
    except Exception:
        logger.exception("Failed to compute player vectors")
        raise HTTPException(status_code=500, detail="Internal server error")

    if player_id not in vectors["player_id"].values:
        raise HTTPException(
            status_code=404,
            detail=f"Player {player_id} not found in season {season_id} data",
        )

    similar = find_similar_players(player_id, vectors, top_n=top_n)

    return [
        SimilarPlayerResponse(
            player_id=int(row["player_id"]),
            player_name=row["player_name"],
            similarity_score=float(row["similarity"]),
            position=None,
        )
        for _, row in similar.iterrows()
    ]


@router.get("/players/{player_id}/development", response_model=DevelopmentResponse)
async def get_player_development(
    player_id: int,
    position_group: str = Query("midfielder", description="Position group for metric selection"),
) -> DevelopmentResponse:
    """Get player development trajectory across seasons."""
    from sqlalchemy import text

    from football_analytics.analysis.development import compute_development_profile
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()

    query = text("""
        SELECT
            e.player_id,
            m.season_id,
            COUNT(DISTINCT e.match_id) AS matches,
            COUNT(DISTINCT e.match_id) * 70 AS minutes_played,
            COUNT(*) FILTER (WHERE e.event_type = 'Shot'
                AND e.shot_outcome = 'Goal') AS goals,
            COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0) AS xg_total,
            COALESCE(SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL), 0) AS xa_total,
            COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots,
            COUNT(*) FILTER (WHERE e.key_pass) AS key_passes,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS passes_completed,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass') AS passes_attempted,
            COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures,
            COUNT(*) FILTER (WHERE e.event_type = 'Tackle') AS tackles,
            COUNT(*) FILTER (WHERE e.event_type = 'Interception') AS interceptions,
            COUNT(*) FILTER (WHERE e.event_type = 'Dribble' AND e.dribble_outcome = 'Complete') AS dribbles_completed,
            COUNT(*) FILTER (WHERE e.event_type = 'Carry') AS carries
        FROM events e
        JOIN matches m ON e.match_id = m.match_id
        WHERE e.player_id = :player_id
        GROUP BY e.player_id, m.season_id
        HAVING COUNT(DISTINCT e.match_id) >= 3
        ORDER BY m.season_id
    """)

    import pandas as pd

    with engine.connect() as conn:
        per90_df = pd.read_sql(query, conn, params={"player_id": player_id})

    if per90_df.empty or len(per90_df) < 2:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient multi-season data for player {player_id}. Need at least 2 seasons with 3+ appearances each.",
        )

    per90_factor = 90.0 / per90_df["minutes_played"].clip(lower=90)
    per90_df["goals_per_90"] = per90_df["goals"] * per90_factor
    per90_df["xg_per_90"] = per90_df["xg_total"] * per90_factor
    per90_df["xa_per_90"] = per90_df["xa_total"] * per90_factor
    per90_df["shots_per_90"] = per90_df["shots"] * per90_factor
    per90_df["key_passes_per_90"] = per90_df["key_passes"] * per90_factor
    per90_df["pressures_per_90"] = per90_df["pressures"] * per90_factor
    per90_df["successful_dribbles_per_90"] = per90_df["dribbles_completed"] * per90_factor
    per90_df["passes_completed_per_90"] = per90_df["passes_completed"] * per90_factor
    per90_df["pass_accuracy"] = per90_df["passes_completed"] / per90_df["passes_attempted"].clip(lower=1)

    with engine.connect() as conn:
        name_row = conn.execute(
            text("SELECT player_name FROM players WHERE player_id = :pid"),
            {"pid": player_id},
        ).fetchone()
    player_name = name_row[0] if name_row else f"Player {player_id}"

    profile = compute_development_profile(
        per90_df,
        player_id=player_id,
        position_group=position_group,
        player_name=player_name,
    )

    return DevelopmentResponse(
        player_id=profile.player_id,
        player_name=profile.player_name,
        trajectory=profile.trajectory,
        seasons_tracked=len(profile.seasons),
        trend_slopes=profile.trend_slopes,
        percentile_changes=profile.percentile_changes,
    )


@router.get("/teams/{team_id}/set-pieces", response_model=TeamSetPieceResponse)
async def get_team_set_pieces(
    team_id: int,
    season_id: int | None = Query(None),
) -> TeamSetPieceResponse:
    """Get set-piece efficiency metrics for a team."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.analysis.set_pieces import (
        compute_set_piece_efficiency,
        extract_set_pieces,
        set_pieces_to_dataframe,
    )
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()

    query = text(
        """
        SELECT e.*, p.player_name
        FROM events e
        LEFT JOIN players p ON e.player_id = p.player_id
        JOIN matches m ON e.match_id = m.match_id
        WHERE e.team_id = :team_id
          AND e.play_pattern IN ('From Corner', 'From Free Kick', 'From Throw In')
    """
        + (" AND m.season_id = :season_id" if season_id else "")
    )

    params: dict[str, Any] = {"team_id": team_id}
    if season_id:
        params["season_id"] = season_id

    with engine.connect() as conn:
        events_df = pd.read_sql(query, conn, params=params)

    if events_df.empty:
        raise HTTPException(status_code=404, detail=f"No set-piece data found for team {team_id}")

    sequences = extract_set_pieces(events_df)
    sp_df = set_pieces_to_dataframe(sequences)
    efficiency = compute_set_piece_efficiency(sp_df, team_id)

    return TeamSetPieceResponse(
        team_id=team_id,
        total_set_pieces=efficiency.get("total_set_pieces", 0),
        corner_count=efficiency.get("corner_count"),
        corner_goal_rate=efficiency.get("corner_goal_rate"),
        free_kick_count=efficiency.get("free_kick_count"),
        free_kick_goal_rate=efficiency.get("free_kick_goal_rate"),
        xg_from_set_pieces=(round(sp_df["xg_generated"].sum(), 2) if not sp_df.empty else 0.0),
    )


@router.get("/teams/{team_id}/possession-profile", response_model=PossessionChainSummary)
async def get_possession_profile(
    team_id: int,
    season_id: int | None = Query(None),
) -> PossessionChainSummary:
    """Get possession chain profile for a team."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.analysis.possession_chains import (
        chains_to_dataframe,
        compute_team_possession_profile,
        extract_possession_chains,
    )
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()

    query = text(
        """
        SELECT e.*
        FROM events e
        JOIN matches m ON e.match_id = m.match_id
        WHERE (m.home_team_id = :team_id OR m.away_team_id = :team_id)
    """
        + (" AND m.season_id = :season_id" if season_id else "")
        + " ORDER BY e.match_id, e.minute, e.second"
    )

    params: dict[str, Any] = {"team_id": team_id}
    if season_id:
        params["season_id"] = season_id

    with engine.connect() as conn:
        events_df = pd.read_sql(query, conn, params=params)

    if events_df.empty:
        raise HTTPException(status_code=404, detail=f"No event data found for team {team_id}")

    chains = extract_possession_chains(events_df)
    chains_df = chains_to_dataframe(chains)
    profile = compute_team_possession_profile(chains_df, team_id)

    if profile["total_chains"] == 0:
        raise HTTPException(status_code=404, detail=f"No possession chains found for team {team_id}")

    return PossessionChainSummary(
        team_id=team_id,
        total_chains=profile["total_chains"],
        avg_chain_length_events=profile.get("avg_chain_length_events", 0.0),
        avg_passes_per_chain=profile.get("avg_passes_per_chain", 0.0),
        final_third_entry_rate=profile.get("final_third_entry_rate", 0.0),
        box_entry_rate=profile.get("box_entry_rate", 0.0),
        dangerous_possession_rate=profile.get("dangerous_possession_rate", 0.0),
        xg_per_chain=profile.get("xg_per_chain", 0.0),
        style_distribution=profile.get("style_distribution", {}),
    )
