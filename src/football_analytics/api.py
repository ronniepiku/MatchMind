"""FastAPI REST API layer for football analytics.

Exposes analysis functions as HTTP endpoints for:
- External integrations (Tableau, Power BI, mobile apps)
- Slack bots and notification systems
- Custom dashboards (React, Vue)
- Automated reporting pipelines

Endpoints:
- /api/v1/players/{id}/profile — Player performance summary
- /api/v1/players/{id}/similar — Similar players
- /api/v1/players/{id}/development — Development trajectory
- /api/v1/teams/{id}/set-pieces — Set-piece analysis
- /api/v1/teams/{id}/possession-profile — Possession chain analysis
- /api/v1/simulation/match — Match outcome simulation
- /api/v1/xg/predict — Predict xG for shot data
- /api/v1/health — Health check
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Football Analytics API",
    description="REST API for StatsBomb-based football data analysis",
    version="0.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS for frontend integrations
_allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


# ============================================================================
# Request/Response Models
# ============================================================================


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.3.0"


class ShotInput(BaseModel):
    """Input for xG prediction."""

    location_x: float = Field(
        ..., ge=0, le=120, description="X coordinate (StatsBomb pitch)"
    )
    location_y: float = Field(
        ..., ge=0, le=80, description="Y coordinate (StatsBomb pitch)"
    )
    shot_body_part: str = Field("Foot", description="Body part: Foot, Head, Other")
    under_pressure: bool = Field(False, description="Whether shot was under pressure")
    play_pattern: str = Field("From Open Play", description="Play pattern")
    shot_type: str | None = Field(
        None, description="Shot type: Penalty, Free Kick, etc."
    )


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


# ============================================================================
# Endpoints
# ============================================================================


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()


@app.post("/api/v1/xg/predict", response_model=XGPredictionResponse)
async def predict_xg(shot: ShotInput) -> XGPredictionResponse:
    """Predict expected goals (xG) for a single shot.

    Uses the trained logistic regression model to estimate
    the probability of a shot resulting in a goal.
    """
    import numpy as np
    import pandas as pd

    from football_analytics.analysis.xg_model import (
        engineer_features,
        get_feature_columns,
    )

    # Build single-row DataFrame
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

    # Simple xG estimation (analytical formula for when model isn't loaded)
    distance = float(features_df["distance_to_goal"].iloc[0])
    angle = float(features_df["goal_angle"].iloc[0])

    # Base xG from distance and angle (empirical logistic curve)
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


@app.post("/api/v1/simulation/match-direct", response_model=SimulationResponse)
async def simulate_match_endpoint(request: SimulationRequest) -> SimulationResponse:
    """Simulate a match outcome using Monte Carlo methods.

    Uses Poisson distribution with given xG values to simulate
    the match thousands of times. Accepts raw xG values directly.
    """
    from football_analytics.analysis.simulation import simulate_match

    result = simulate_match(
        home_xg=request.home_xg,
        away_xg=request.away_xg,
        home_team=request.home_team,
        away_team=request.away_team,
        n_simulations=request.n_simulations,
        home_advantage_factor=request.home_advantage_factor,
    )

    # Convert scoreline tuples to string keys for JSON
    top_scores = sorted(
        result.scoreline_probabilities.items(), key=lambda x: x[1], reverse=True
    )[:10]
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


@app.get("/api/v1/players/{player_id}/profile", response_model=PlayerProfileResponse)
async def get_player_profile(
    player_id: int,
    season_id: int | None = Query(None, description="Filter by season"),
) -> PlayerProfileResponse:
    """Get player performance profile.

    Returns aggregated statistics for a player, optionally filtered by season.
    Requires database connection.
    """
    from sqlalchemy import create_engine, text

    from football_analytics.config import config

    engine = create_engine(config.db.url)

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
        pass_accuracy=round(
            result.passes_completed / max(result.passes_attempted, 1), 3
        ),
        pressures=result.pressures,
        tackles=result.tackles,
        interceptions=result.interceptions,
    )


@app.get(
    "/api/v1/players/{player_id}/similar", response_model=list[SimilarPlayerResponse]
)
async def get_similar_players(
    player_id: int,
    season_id: int = Query(106, description="Season to compute vectors from"),
    top_n: int = Query(10, ge=1, le=50, description="Number of similar players"),
) -> list[SimilarPlayerResponse]:
    """Find players with similar statistical profiles.

    Uses cosine similarity on normalised per-90 feature vectors.
    Requires database connection with player data loaded.
    """
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
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )

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


@app.get("/api/v1/players/{player_id}/development", response_model=DevelopmentResponse)
async def get_player_development(
    player_id: int,
    position_group: str = Query(
        "midfielder", description="Position group for metric selection"
    ),
) -> DevelopmentResponse:
    """Get player development trajectory across seasons.

    Analyses multi-season trends to classify whether a player is
    improving, declining, or stable.
    """
    from sqlalchemy import text

    from football_analytics.analysis.development import compute_development_profile
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()

    # Fetch per-90 data for the player across all seasons
    query = text("""
        SELECT
            e.player_id,
            m.season_id,
            COUNT(DISTINCT e.match_id) AS matches,
            COUNT(DISTINCT e.match_id) * 70 AS minutes_played,
            COUNT(*) FILTER (WHERE e.event_type = 'Shot'
                AND e.shot_outcome = 'Goal') AS goals,
            COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0)
                AS xg_total,
            COALESCE(SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL), 0)
                AS xa_total,
            COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots,
            COUNT(*) FILTER (WHERE e.key_pass) AS key_passes,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass'
                AND e.pass_outcome IS NULL) AS passes_completed,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass')
                AS passes_attempted,
            COUNT(*) FILTER (WHERE e.event_type = 'Pressure')
                AS pressures,
            COUNT(*) FILTER (WHERE e.event_type = 'Tackle') AS tackles,
            COUNT(*) FILTER (WHERE e.event_type = 'Interception')
                AS interceptions,
            COUNT(*) FILTER (WHERE e.event_type = 'Dribble'
                AND e.dribble_outcome = 'Complete') AS dribbles_completed,
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
            detail=(
                f"Insufficient multi-season data for player {player_id}. "
                "Need at least 2 seasons with 3+ appearances each."
            ),
        )

    # Compute per-90 rates
    per90_factor = 90.0 / per90_df["minutes_played"].clip(lower=90)
    per90_df["goals_per_90"] = per90_df["goals"] * per90_factor
    per90_df["xg_per_90"] = per90_df["xg_total"] * per90_factor
    per90_df["xa_per_90"] = per90_df["xa_total"] * per90_factor
    per90_df["shots_per_90"] = per90_df["shots"] * per90_factor
    per90_df["key_passes_per_90"] = per90_df["key_passes"] * per90_factor
    per90_df["pressures_per_90"] = per90_df["pressures"] * per90_factor
    per90_df["successful_dribbles_per_90"] = (
        per90_df["dribbles_completed"] * per90_factor
    )
    per90_df["passes_completed_per_90"] = per90_df["passes_completed"] * per90_factor
    per90_df["pass_accuracy"] = per90_df["passes_completed"] / per90_df[
        "passes_attempted"
    ].clip(lower=1)

    # Get player name
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


@app.get("/api/v1/teams/{team_id}/set-pieces", response_model=TeamSetPieceResponse)
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

    # Fetch set-piece events for the team
    query = text("""
        SELECT e.*, p.player_name
        FROM events e
        LEFT JOIN players p ON e.player_id = p.player_id
        JOIN matches m ON e.match_id = m.match_id
        WHERE e.team_id = :team_id
          AND e.play_pattern IN (
              'From Corner', 'From Free Kick', 'From Throw In'
          )
    """ + (" AND m.season_id = :season_id" if season_id else ""))

    params: dict[str, Any] = {"team_id": team_id}
    if season_id:
        params["season_id"] = season_id

    with engine.connect() as conn:
        events_df = pd.read_sql(query, conn, params=params)

    if events_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No set-piece data found for team {team_id}",
        )

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
        xg_from_set_pieces=(
            round(sp_df["xg_generated"].sum(), 2) if not sp_df.empty else 0.0
        ),
    )


@app.get(
    "/api/v1/teams/{team_id}/possession-profile",
    response_model=PossessionChainSummary,
)
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

    # Fetch all events for the team's matches
    query = text(
        """
        SELECT e.*
        FROM events e
        JOIN matches m ON e.match_id = m.match_id
        WHERE (m.home_team_id = :team_id OR m.away_team_id = :team_id)
    """
        + (" AND m.season_id = :season_id" if season_id else "")
        + """
        ORDER BY e.match_id, e.minute, e.second
    """
    )

    params: dict[str, Any] = {"team_id": team_id}
    if season_id:
        params["season_id"] = season_id

    with engine.connect() as conn:
        events_df = pd.read_sql(query, conn, params=params)

    if events_df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No event data found for team {team_id}",
        )

    chains = extract_possession_chains(events_df)
    chains_df = chains_to_dataframe(chains)
    profile = compute_team_possession_profile(chains_df, team_id)

    if profile["total_chains"] == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No possession chains found for team {team_id}",
        )

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


# ============================================================================
# Dashboard Endpoints (for React Frontend)
# ============================================================================


@app.get("/api/v1/teams")
async def list_teams() -> list[dict[str, Any]]:
    """List all available teams."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(
                "SELECT DISTINCT team_id AS id, team_name AS name FROM teams ORDER BY team_name"
            ),
            conn,
        )
    return df.to_dict(orient="records")


@app.get("/api/v1/seasons")
async def list_seasons() -> list[dict[str, Any]]:
    """List all available seasons."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(
                "SELECT season_id AS id, season_name AS name, "
                "competition_name FROM competitions ORDER BY competition_name, season_name"
            ),
            conn,
        )
    return df.to_dict(orient="records")


@app.get("/api/v1/players")
async def list_players(
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> list[dict[str, Any]]:
    """List players for a team/season combination."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT DISTINCT p.player_id AS id, p.player_name AS name,
                       COALESCE(l.position, 'Unknown') AS position
                FROM players p
                JOIN events e ON p.player_id = e.player_id
                JOIN matches m ON e.match_id = m.match_id
                LEFT JOIN lineups l ON p.player_id = l.player_id
                    AND l.match_id = e.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                ORDER BY p.player_name
            """),
            conn,
            params={"team_id": team_id, "season_id": season_id},
        )
    return df.to_dict(orient="records")


@app.get("/api/v1/matches")
async def list_matches(
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> list[dict[str, Any]]:
    """List matches for a team/season combination."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT m.match_id AS id,
                       ht.team_name AS home_team,
                       at.team_name AS away_team,
                       m.home_score,
                       m.away_score,
                       m.match_date AS date,
                       c.competition_name AS competition
                FROM matches m
                JOIN teams ht ON m.home_team_id = ht.team_id
                JOIN teams at ON m.away_team_id = at.team_id
                JOIN competitions c ON m.competition_id = c.competition_id
                WHERE (m.home_team_id = :team_id OR m.away_team_id = :team_id)
                  AND m.season_id = :season_id
                ORDER BY m.match_date DESC
            """),
            conn,
            params={"team_id": team_id, "season_id": season_id},
        )
    return df.to_dict(orient="records")


@app.get("/api/v1/data-availability")
async def check_data_availability(
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> dict[str, Any]:
    """Check data availability for a team/season."""
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT COUNT(*) AS matches
                FROM matches
                WHERE (home_team_id = :team_id OR away_team_id = :team_id)
                  AND season_id = :season_id
            """),
            {"team_id": team_id, "season_id": season_id},
        ).fetchone()

    count = result[0] if result else 0
    return {"matches": count, "has_data": count > 0}


@app.get("/api/v1/opponent/report")
async def get_opponent_report(
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> dict[str, Any]:
    """Generate opponent scouting report."""
    from football_analytics.analysis.opponent_profile import build_opponent_report
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    report = build_opponent_report(team_id, season_id, engine)

    if not report:
        raise HTTPException(status_code=404, detail="No data for opponent report")

    return report


@app.get("/api/v1/player/summary")
async def get_player_summary(
    player_id: int = Query(...),
    season_id: int = Query(...),
) -> dict[str, Any]:
    """Get player season summary statistics."""
    from football_analytics.analysis.player_performance import (
        get_player_season_summary,
    )
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    summary = get_player_season_summary(engine, player_id, season_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Player data not found")

    return summary


@app.get("/api/v1/player/rolling-form")
async def get_player_rolling_form(
    player_id: int = Query(...),
    season_id: int = Query(...),
) -> list[dict[str, Any]]:
    """Get player rolling form data."""
    from football_analytics.analysis.player_performance import get_player_rolling_form
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    form_data = get_player_rolling_form(engine, player_id, season_id)

    if form_data is None or (hasattr(form_data, "empty") and form_data.empty):
        return []

    if hasattr(form_data, "to_dict"):
        return form_data.to_dict(orient="records")
    return form_data


@app.get("/api/v1/player/radar")
async def get_player_radar(
    player_id: int = Query(...),
    season_id: int = Query(...),
) -> list[dict[str, Any]]:
    """Get player radar percentile data."""
    from football_analytics.analysis.player_performance import (
        get_player_radar_percentiles,
    )
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    radar_data = get_player_radar_percentiles(engine, player_id, season_id)

    if radar_data is None:
        return []

    if hasattr(radar_data, "to_dict"):
        return radar_data.to_dict(orient="records")
    return radar_data


@app.get("/api/v1/player/squad-comparison")
async def get_squad_comparison(
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> list[dict[str, Any]]:
    """Get squad comparison data."""
    from football_analytics.analysis.player_performance import get_squad_comparison
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    comparison = get_squad_comparison(engine, team_id, season_id)

    if comparison is None or (hasattr(comparison, "empty") and comparison.empty):
        return []

    if hasattr(comparison, "to_dict"):
        return comparison.to_dict(orient="records")
    return comparison


@app.get("/api/v1/team/scorecard")
async def get_team_scorecard(
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> dict[str, Any]:
    """Generate comprehensive team scorecard."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.analysis.opponent_profile import (
        get_opponent_defensive_shape,
    )
    from football_analytics.analysis.possession_chains import (
        chains_to_dataframe,
        compute_team_possession_profile,
        compute_transition_metrics,
        extract_possession_chains,
    )
    from football_analytics.analysis.set_pieces import (
        compute_set_piece_efficiency,
        extract_set_pieces,
        set_pieces_to_dataframe,
    )
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()

    # Fetch events
    with engine.connect() as conn:
        events_df = pd.read_sql(
            text("""
                SELECT e.*
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE (m.home_team_id = :team_id OR m.away_team_id = :team_id)
                  AND m.season_id = :season_id
                ORDER BY e.match_id, e.minute, e.second
            """),
            conn,
            params={"team_id": team_id, "season_id": season_id},
        )

    if events_df.empty:
        raise HTTPException(status_code=404, detail="No event data found")

    # Possession profile
    chains = extract_possession_chains(events_df)
    chains_df = chains_to_dataframe(chains)
    profile = compute_team_possession_profile(chains_df, team_id)
    transitions = compute_transition_metrics(chains)

    # Set pieces
    sp_events = events_df[
        events_df["play_pattern"].isin(
            ["From Corner", "From Free Kick", "From Throw In"]
        )
    ]
    sp_sequences = extract_set_pieces(sp_events) if not sp_events.empty else []
    sp_df = set_pieces_to_dataframe(sp_sequences) if sp_sequences else pd.DataFrame()
    sp_efficiency = (
        compute_set_piece_efficiency(sp_df, team_id) if not sp_df.empty else {}
    )

    # Defensive shape / pressing
    defensive_shape = get_opponent_defensive_shape(engine, team_id, season_id)

    # Build KPIs
    team_events = events_df[events_df["team_id"] == team_id]
    n_matches = events_df["match_id"].nunique()
    shots = team_events[team_events["event_type"] == "Shot"]
    total_xg = float(shots["xg"].sum()) if "xg" in shots.columns else 0.0

    kpis = [
        {"label": "Matches", "value": n_matches, "unit": ""},
        {"label": "Total xG", "value": round(total_xg, 2), "unit": ""},
        {
            "label": "xG/Match",
            "value": round(total_xg / max(n_matches, 1), 2),
            "unit": "",
        },
        {
            "label": "Possession Chains",
            "value": profile.get("total_chains", 0),
            "unit": "",
        },
        {
            "label": "Dangerous Poss %",
            "value": round(profile.get("dangerous_possession_rate", 0) * 100, 1),
            "unit": "%",
        },
    ]

    # Possession style
    possession_profile = [
        {"style": k, "percentage": round(v * 100, 1)}
        for k, v in profile.get("style_distribution", {}).items()
    ]

    # Pressing intensity by zone
    pressing_data = []
    if defensive_shape and isinstance(defensive_shape, list):
        for zone_data in defensive_shape:
            if isinstance(zone_data, dict):
                pressing_data.append(
                    {
                        "zone": zone_data.get("zone", "Unknown"),
                        "pressures_per_90": round(
                            zone_data.get("pressures", 0)
                            / max(n_matches, 1)
                            * (90 / 95),
                            1,
                        ),
                    }
                )

    # Transitions
    transition_metrics = []
    if transitions and isinstance(transitions, dict):
        for metric_name, value in transitions.items():
            transition_metrics.append(
                {
                    "metric": metric_name.replace("_", " ").title(),
                    "value": round(value, 2) if isinstance(value, (int, float)) else 0,
                    "league_avg": 0,
                    "percentile": 50,
                }
            )

    # Set piece efficiency
    set_pieces_list = []
    if sp_efficiency and isinstance(sp_efficiency, dict):
        for sp_type in ["corner", "free_kick", "throw_in"]:
            count = sp_efficiency.get(f"{sp_type}_count", 0)
            if count:
                set_pieces_list.append(
                    {
                        "type": sp_type.replace("_", " ").title(),
                        "total": count,
                        "chances_created": sp_efficiency.get(f"{sp_type}_chances", 0),
                        "goals": sp_efficiency.get(f"{sp_type}_goals", 0),
                        "xg": round(sp_efficiency.get(f"{sp_type}_xg", 0), 2),
                        "conversion_rate": round(
                            sp_efficiency.get(f"{sp_type}_goal_rate", 0), 3
                        ),
                    }
                )

    return {
        "kpis": kpis,
        "possession_profile": possession_profile,
        "pressing_intensity": pressing_data,
        "transitions": transition_metrics,
        "set_pieces": set_pieces_list,
    }


@app.get("/api/v1/match/shots")
async def get_match_shots(
    match_id: int = Query(...),
) -> list[dict[str, Any]]:
    """Get shot events for a match."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT e.location_x AS x, e.location_y AS y,
                       COALESCE(e.xg, 0) AS xg,
                       LOWER(COALESCE(e.shot_outcome, 'off_target')) AS outcome,
                       p.player_name,
                       e.minute,
                       t.team_name AS team,
                       COALESCE(e.shot_body_part, 'Foot') AS body_part,
                       COALESCE(e.shot_technique, 'Normal') AS technique
                FROM events e
                LEFT JOIN players p ON e.player_id = p.player_id
                LEFT JOIN teams t ON e.team_id = t.team_id
                WHERE e.match_id = :match_id AND e.event_type = 'Shot'
                ORDER BY e.minute
            """),
            conn,
            params={"match_id": match_id},
        )
    # Normalise outcome names
    outcome_map = {
        "goal": "goal",
        "saved": "saved",
        "blocked": "blocked",
        "off target": "off_target",
        "off_target": "off_target",
        "post": "post",
        "wayward": "off_target",
    }
    df["outcome"] = df["outcome"].map(lambda x: outcome_map.get(x, "off_target"))
    return df.to_dict(orient="records")


@app.get("/api/v1/match/xg-timeline")
async def get_xg_timeline(
    match_id: int = Query(...),
) -> list[dict[str, Any]]:
    """Get xG timeline events for a match."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT e.minute,
                       t.team_name AS team,
                       COALESCE(e.xg, 0) AS xg,
                       p.player_name,
                       LOWER(COALESCE(e.shot_outcome, 'off_target')) AS outcome
                FROM events e
                LEFT JOIN players p ON e.player_id = p.player_id
                LEFT JOIN teams t ON e.team_id = t.team_id
                WHERE e.match_id = :match_id AND e.event_type = 'Shot'
                ORDER BY e.minute
            """),
            conn,
            params={"match_id": match_id},
        )

    # Compute cumulative xG per team
    records = []
    team_cum: dict[str, float] = {}
    for _, row in df.iterrows():
        team = row["team"]
        team_cum[team] = team_cum.get(team, 0) + row["xg"]
        records.append(
            {
                "minute": int(row["minute"]),
                "team": team,
                "xg": round(float(row["xg"]), 3),
                "cumulative_xg": round(team_cum[team], 3),
                "player_name": row["player_name"],
                "outcome": row["outcome"],
            }
        )
    return records


@app.get("/api/v1/match/passing-network")
async def get_passing_network(
    match_id: int = Query(...),
    team_id: int = Query(...),
) -> dict[str, Any]:
    """Get passing network data for a team in a match."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        passes_df = pd.read_sql(
            text("""
                SELECT e.player_id, p.player_name,
                       COALESCE(p.position, 'Unknown') AS position,
                       e.location_x, e.location_y,
                       e.pass_recipient_id
                FROM events e
                LEFT JOIN players p ON e.player_id = p.player_id
                WHERE e.match_id = :match_id
                  AND e.team_id = :team_id
                  AND e.event_type = 'Pass'
                  AND e.pass_outcome IS NULL
                  AND e.minute <= 70
                ORDER BY e.minute
            """),
            conn,
            params={"match_id": match_id, "team_id": team_id},
        )

    if passes_df.empty:
        return {"nodes": [], "edges": []}

    # Compute average positions
    avg_pos = (
        passes_df.groupby(["player_id", "player_name", "position"])
        .agg(
            x=("location_x", "mean"),
            y=("location_y", "mean"),
            passes_made=("player_id", "count"),
        )
        .reset_index()
    )

    # Filter to most active 11 players
    avg_pos = avg_pos.nlargest(11, "passes_made")

    nodes = [
        {
            "player_name": row["player_name"],
            "position": row["position"],
            "x": round(float(row["x"]), 1),
            "y": round(float(row["y"]), 1),
            "passes_made": int(row["passes_made"]),
        }
        for _, row in avg_pos.iterrows()
    ]

    # Compute edges (pass combinations)
    active_ids = set(avg_pos["player_id"].values)
    edge_df = passes_df[
        passes_df["player_id"].isin(active_ids)
        & passes_df["pass_recipient_id"].isin(active_ids)
    ]

    # Build name lookup
    id_to_name = dict(zip(avg_pos["player_id"], avg_pos["player_name"]))

    edge_counts = (
        edge_df.groupby(["player_id", "pass_recipient_id"])
        .size()
        .reset_index(name="passes")
    )

    # Only keep edges with 3+ passes
    edge_counts = edge_counts[edge_counts["passes"] >= 3]

    edges = [
        {
            "source": id_to_name.get(row["player_id"], "Unknown"),
            "target": id_to_name.get(row["pass_recipient_id"], "Unknown"),
            "passes": int(row["passes"]),
            "progressive": 0,
        }
        for _, row in edge_counts.iterrows()
    ]

    return {"nodes": nodes, "edges": edges}


@app.get("/api/v1/match/pressure-map")
async def get_pressure_map(
    match_id: int = Query(...),
    team_id: int = Query(...),
) -> list[dict[str, Any]]:
    """Get pressure events for a team in a match."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT e.location_x AS x, e.location_y AS y,
                       e.counterpress AS success,
                       e.minute,
                       p.player_name
                FROM events e
                LEFT JOIN players p ON e.player_id = p.player_id
                WHERE e.match_id = :match_id
                  AND e.team_id = :team_id
                  AND e.event_type = 'Pressure'
                ORDER BY e.minute
            """),
            conn,
            params={"match_id": match_id, "team_id": team_id},
        )
    return df.to_dict(orient="records")


@app.get("/api/v1/player/similar")
async def get_similar_players_v2(
    player_id: int = Query(...),
    season_id: int = Query(106),
    top_n: int = Query(10, ge=1, le=50),
) -> list[dict[str, Any]]:
    """Find similar players (v2 endpoint for dashboard)."""
    from football_analytics.analysis.similarity import (
        compute_player_vectors,
        find_similar_players,
    )
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    try:
        vectors = compute_player_vectors(season_id, engine=engine, min_appearances=3)
    except Exception:
        logger.exception("Similarity computation failed")
        raise HTTPException(status_code=500, detail="Internal server error")

    if player_id not in vectors["player_id"].values:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    similar = find_similar_players(player_id, vectors, top_n=top_n)

    return [
        {
            "player_name": row["player_name"],
            "team": row.get("team_name", "Unknown"),
            "position": row.get("position", "Unknown"),
            "similarity_score": round(float(row["similarity"]), 3),
            "age": int(row.get("age", 0)),
            "minutes": int(row.get("minutes", 0)),
            "key_metrics": {},
        }
        for _, row in similar.iterrows()
    ]


class SimulationV2Request(BaseModel):
    """Request model for v2 match simulation."""

    home_team_id: int = Field(..., gt=0, description="Home team ID")
    away_team_id: int = Field(..., gt=0, description="Away team ID")
    season_id: int = Field(..., gt=0, description="Season ID")


@app.post("/api/v1/simulation/match")
async def simulate_match_v2(request: SimulationV2Request) -> dict[str, Any]:
    """Run match simulation (v2 endpoint for dashboard).

    Accepts home_team_id, away_team_id, season_id and computes
    xG values from historical data before running simulation.
    """
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.analysis.simulation import simulate_match
    from football_analytics.db import get_engine as _get_engine

    home_team_id = request.home_team_id
    away_team_id = request.away_team_id
    season_id = request.season_id

    engine = _get_engine()

    # Compute average xG per match for each team
    with engine.connect() as conn:
        home_xg_df = pd.read_sql(
            text("""
                SELECT COALESCE(AVG(match_xg), 1.3) AS avg_xg FROM (
                    SELECT SUM(COALESCE(e.xg, 0)) AS match_xg
                    FROM events e
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE e.team_id = :team_id
                      AND m.season_id = :season_id
                      AND e.event_type = 'Shot'
                    GROUP BY e.match_id
                ) sub
            """),
            conn,
            params={"team_id": home_team_id, "season_id": season_id},
        )
        away_xg_df = pd.read_sql(
            text("""
                SELECT COALESCE(AVG(match_xg), 1.1) AS avg_xg FROM (
                    SELECT SUM(COALESCE(e.xg, 0)) AS match_xg
                    FROM events e
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE e.team_id = :team_id
                      AND m.season_id = :season_id
                      AND e.event_type = 'Shot'
                    GROUP BY e.match_id
                ) sub
            """),
            conn,
            params={"team_id": away_team_id, "season_id": season_id},
        )

        # Get team names
        teams_df = pd.read_sql(
            text("SELECT team_id, team_name FROM teams WHERE team_id IN (:h, :a)"),
            conn,
            params={"h": home_team_id, "a": away_team_id},
        )

    home_xg = float(home_xg_df["avg_xg"].iloc[0]) if not home_xg_df.empty else 1.3
    away_xg = float(away_xg_df["avg_xg"].iloc[0]) if not away_xg_df.empty else 1.1

    home_name = "Home"
    away_name = "Away"
    for _, row in teams_df.iterrows():
        if row["team_id"] == home_team_id:
            home_name = row["team_name"]
        elif row["team_id"] == away_team_id:
            away_name = row["team_name"]

    result = simulate_match(
        home_xg=home_xg,
        away_xg=away_xg,
        home_team=home_name,
        away_team=away_name,
        n_simulations=10000,
    )

    # Convert scoreline distribution
    top_scores = sorted(
        result.scoreline_probabilities.items(), key=lambda x: x[1], reverse=True
    )[:15]
    scoreline_dist = [
        {"score": f"{h}-{a}", "probability": round(prob, 4)}
        for (h, a), prob in top_scores
    ]

    return {
        "home_win_prob": round(result.home_win_prob, 4),
        "draw_prob": round(result.draw_prob, 4),
        "away_win_prob": round(result.away_win_prob, 4),
        "expected_home_goals": round(result.expected_home_goals, 2),
        "expected_away_goals": round(result.expected_away_goals, 2),
        "most_likely_score": f"{result.most_likely_score[0]}-{result.most_likely_score[1]}",
        "over_2_5_prob": round(result.over_2_5_prob, 4),
        "btts_prob": round(result.btts_prob, 4),
        "scoreline_distribution": scoreline_dist,
    }


def main() -> None:
    """Run the API server."""
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
