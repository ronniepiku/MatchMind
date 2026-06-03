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
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ─── Rate Limiter Setup ─────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(
    title="Football Analytics API",
    description="REST API for StatsBomb-based football data analysis",
    version="0.5.0",
    docs_url="/docs" if os.getenv("API_DOCS_ENABLED", "true").lower() == "true" else None,
    redoc_url="/redoc" if os.getenv("API_DOCS_ENABLED", "true").lower() == "true" else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ─── Request Logging Middleware ─────────────────────────────────────────────


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


app.add_middleware(RequestLoggingMiddleware)


# ─── Global Exception Handler ───────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions — never leak stack traces to clients."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# CORS for frontend integrations
_allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173",
).split(",")
_validated_origins = [o.strip() for o in _allowed_origins if o.strip().startswith(("http://", "https://"))]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_validated_origins,
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
@limiter.limit("20/minute")
async def simulate_match_endpoint(request: Request, sim_req: SimulationRequest) -> SimulationResponse:
    """Simulate a match outcome using Monte Carlo methods.

    Uses Poisson distribution with given xG values to simulate
    the match thousands of times. Accepts raw xG values directly.
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

    # Convert scoreline tuples to string keys for JSON
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
        pass_accuracy=round(result.passes_completed / max(result.passes_attempted, 1), 3),
        pressures=result.pressures,
        tackles=result.tackles,
        interceptions=result.interceptions,
    )


@app.get("/api/v1/players/{player_id}/similar", response_model=list[SimilarPlayerResponse])
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
    position_group: str = Query("midfielder", description="Position group for metric selection"),
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
    per90_df["successful_dribbles_per_90"] = per90_df["dribbles_completed"] * per90_factor
    per90_df["passes_completed_per_90"] = per90_df["passes_completed"] * per90_factor
    per90_df["pass_accuracy"] = per90_df["passes_completed"] / per90_df["passes_attempted"].clip(lower=1)

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
    query = text(
        """
        SELECT e.*, p.player_name
        FROM events e
        LEFT JOIN players p ON e.player_id = p.player_id
        JOIN matches m ON e.match_id = m.match_id
        WHERE e.team_id = :team_id
          AND e.play_pattern IN (
              'From Corner', 'From Free Kick', 'From Throw In'
          )
    """
        + (" AND m.season_id = :season_id" if season_id else "")
    )

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
        xg_from_set_pieces=(round(sp_df["xg_generated"].sum(), 2) if not sp_df.empty else 0.0),
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
            text("SELECT DISTINCT team_id AS id, team_name AS name FROM teams ORDER BY team_name"),
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
    from sqlalchemy import text as _text

    from football_analytics.analysis.opponent_profile import build_opponent_report
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    report = build_opponent_report(team_id, season_id, engine)

    if report is None:
        raise HTTPException(status_code=404, detail="No data for opponent report")

    # Get team name
    with engine.connect() as conn:
        team_row = conn.execute(
            _text("SELECT team_name FROM teams WHERE team_id = :tid"),
            {"tid": team_id},
        ).fetchone()
    team_name = team_row[0] if team_row else "Unknown"

    # Transform attack_patterns DataFrame to frontend format
    attack_patterns = []
    ap_df = report.get("attack_patterns")
    if ap_df is not None and hasattr(ap_df, "empty") and not ap_df.empty:
        for _, row in ap_df.iterrows():
            possessions = int(row.get("possessions", 0))
            shots = int(row.get("shots", 0))
            int(row.get("goals", 0))
            success_rate = shots / max(possessions, 1)
            attack_patterns.append(
                {
                    "pattern_type": row.get("play_pattern", "Unknown"),
                    "frequency": possessions,
                    "success_rate": round(success_rate, 3),
                    "xg_per_attack": round(float(row.get("avg_xg", 0) or 0), 3),
                }
            )

    # Transform defensive_shape DataFrame
    defensive_shape = []
    ds_df = report.get("defensive_shape")
    if ds_df is not None and hasattr(ds_df, "empty") and not ds_df.empty:
        for _, row in ds_df.iterrows():
            defensive_shape.append(
                {
                    "zone": row.get("zone", "Unknown"),
                    "tackles": int(row.get("tackles", 0)),
                    "interceptions": int(row.get("interceptions", 0)),
                    "pressures": int(row.get("pressures", 0)),
                    "recoveries": int(row.get("blocks", 0)),
                }
            )

    # Transform key_players DataFrame
    key_players = []
    kp_df = report.get("key_players")
    if kp_df is not None and hasattr(kp_df, "empty") and not kp_df.empty:
        for _, row in kp_df.iterrows():
            xg = float(row.get("total_xg", 0) or 0)
            xa = float(row.get("total_xa", 0) or 0)
            matches = int(row.get("matches", 1))
            threat = round((xg + xa) / max(matches, 1) * 10, 1)
            key_players.append(
                {
                    "player_name": row.get("player_name", "Unknown"),
                    "position": "FW",
                    "goals": int(row.get("shots", 0)),
                    "assists": int(row.get("key_passes", 0)),
                    "xg": round(xg, 2),
                    "xa": round(xa, 2),
                    "minutes": matches * 90,
                    "threat_rating": min(threat, 10.0),
                }
            )

    return {
        "team_name": team_name,
        "attack_patterns": attack_patterns,
        "defensive_shape": defensive_shape,
        "key_players": key_players,
    }


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
    summary_df = get_player_season_summary(engine, player_id, season_id)

    if summary_df is None or (hasattr(summary_df, "empty") and summary_df.empty):
        raise HTTPException(status_code=404, detail="Player data not found")

    row = summary_df.iloc[0]
    appearances = int(row.get("appearances", 0))
    total_xg = float(row.get("total_xg", 0) or 0)
    total_xa = float(row.get("total_xa", 0) or 0)
    # Estimate minutes as appearances * 90 (no minutes data available)
    minutes = appearances * 90

    return {
        "matches_played": appearances,
        "minutes": minutes,
        "goals": int(row.get("goals", 0)),
        "assists": int(row.get("assists", 0)),
        "xg": round(total_xg, 2),
        "xa": round(total_xa, 2),
        "xg_per_90": round(total_xg / max(appearances, 1), 2),
        "xa_per_90": round(total_xa / max(appearances, 1), 2),
        "passes_completed": int(row.get("passes_completed", 0)),
        "pass_accuracy": round(float(row.get("pass_accuracy", 0) or 0) * 100, 1),
        "tackles_won": int(row.get("tackles", 0)),
        "interceptions": int(row.get("interceptions", 0)),
        "pressures": int(row.get("pressures", 0)),
    }


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

    # Map to frontend expected format
    results = []
    for _, row in form_data.iterrows():
        match_date = str(row.get("match_date", ""))
        results.append(
            {
                "match_date": match_date,
                "match_label": match_date[:10] if match_date else "",
                "xg": round(float(row.get("match_xg", 0) or 0), 3),
                "xa": round(float(row.get("match_xa", 0) or 0), 3),
                "xg_rolling": round(float(row.get("rolling_xg", 0) or 0), 3),
                "xa_rolling": round(float(row.get("rolling_xa", 0) or 0), 3),
            }
        )
    return results


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

    if radar_data is None or (hasattr(radar_data, "empty") and radar_data.empty):
        return []

    # Transform from flat {metric: percentile} row to [{metric, value, percentile}]
    row = radar_data.iloc[0]
    metric_labels = {
        "xg_per_match": "xG per Match",
        "xa_per_match": "xA per Match",
        "passes_per_match": "Passes",
        "dribbles_per_match": "Dribbles",
        "pressures_per_match": "Pressures",
        "def_actions_per_match": "Defensive Actions",
    }
    results = []
    for col, label in metric_labels.items():
        if col in row.index:
            pct = float(row[col])
            results.append(
                {
                    "metric": label,
                    "value": round(pct, 1),
                    "percentile": round(pct, 1),
                }
            )
    return results


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

    # Map to frontend expected format
    results = []
    for _, row in comparison.iterrows():
        appearances = int(row.get("appearances", 1))
        total_xg = float(row.get("total_xg", 0) or 0)
        total_xa = float(row.get("total_xa", 0) or 0)
        goals = int(row.get("goals", 0))
        assists = int(row.get("assists", 0))
        xg_per_90 = total_xg / max(appearances, 1)
        xa_per_90 = total_xa / max(appearances, 1)
        # Rating: weighted combination of offensive output
        rating = min(10.0, round((xg_per_90 + xa_per_90) * 5 + 4, 1))
        results.append(
            {
                "player_name": row.get("player_name", "Unknown"),
                "position": "MF",
                "minutes": appearances * 90,
                "goals": goals,
                "assists": assists,
                "xg_per_90": round(xg_per_90, 2),
                "xa_per_90": round(xa_per_90, 2),
                "rating": rating,
            }
        )
    return results


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
    sp_events = events_df[events_df["play_pattern"].isin(["From Corner", "From Free Kick", "From Throw In"])]
    sp_sequences = extract_set_pieces(sp_events) if not sp_events.empty else []
    sp_df = set_pieces_to_dataframe(sp_sequences) if sp_sequences else pd.DataFrame()
    sp_efficiency = compute_set_piece_efficiency(sp_df, team_id) if not sp_df.empty else {}

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
        {"style": k, "percentage": round(v * 100, 1)} for k, v in profile.get("style_distribution", {}).items()
    ]

    # Pressing intensity by zone
    pressing_data = []
    if defensive_shape is not None and hasattr(defensive_shape, "iterrows") and not defensive_shape.empty:
        for _, zone_data in defensive_shape.iterrows():
            pressing_data.append(
                {
                    "zone": zone_data.get("zone", "Unknown"),
                    "pressures_per_90": round(
                        int(zone_data.get("pressures", 0)) / max(n_matches, 1) * (90 / 95),
                        1,
                    ),
                }
            )
    elif isinstance(defensive_shape, list):
        for zone_data in defensive_shape:
            if isinstance(zone_data, dict):
                pressing_data.append(
                    {
                        "zone": zone_data.get("zone", "Unknown"),
                        "pressures_per_90": round(
                            zone_data.get("pressures", 0) / max(n_matches, 1) * (90 / 95),
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
                        "conversion_rate": round(sp_efficiency.get(f"{sp_type}_goal_rate", 0), 3),
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
    edge_df = passes_df[passes_df["player_id"].isin(active_ids) & passes_df["pass_recipient_id"].isin(active_ids)]

    # Build name lookup
    id_to_name = dict(zip(avg_pos["player_id"], avg_pos["player_name"], strict=False))

    edge_counts = edge_df.groupby(["player_id", "pass_recipient_id"]).size().reset_index(name="passes")

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
@limiter.limit("20/minute")
async def simulate_match_v2(request: Request, sim_req: SimulationV2Request) -> dict[str, Any]:
    """Run match simulation (v2 endpoint for dashboard).

    Accepts home_team_id, away_team_id, season_id and computes
    xG values from historical data before running simulation.
    """
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.analysis.simulation import simulate_match
    from football_analytics.db import get_engine as _get_engine

    home_team_id = sim_req.home_team_id
    away_team_id = sim_req.away_team_id
    season_id = sim_req.season_id

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
    top_scores = sorted(result.scoreline_probabilities.items(), key=lambda x: x[1], reverse=True)[:15]
    scoreline_dist = [{"score": f"{h}-{a}", "probability": round(prob, 4)} for (h, a), prob in top_scores]

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


# ============================================================================
# Prediction Engine Endpoints
# ============================================================================


class MatchPredictionRequest(BaseModel):
    """Request body for match prediction."""

    team_a_id: int = Field(..., description="First team ID")
    team_b_id: int = Field(..., description="Second team ID")
    competition_id: int | None = Field(None, description="Competition context for ratings")
    venue_type: str = Field("neutral", description="Venue: 'home', 'away', 'neutral'")
    n_simulations: int = Field(10000, ge=100, le=100000)


class TournamentSimulationRequest(BaseModel):
    """Request body for tournament simulation."""

    competition_id: int = Field(..., description="Competition ID")
    format_type: str = Field(..., description="Format: 'league', 'groups_knockout', 'knockout'")
    groups: list[dict[str, Any]] | None = Field(None, description="Group configurations")
    team_ids: list[int] | None = Field(None, description="Team IDs (for league/knockout)")
    n_simulations: int = Field(10000, ge=100, le=100000)
    best_third_place_count: int = Field(0, ge=0)
    knockout_rounds: int = Field(0, ge=0)


@app.post("/api/v1/predict/match")
@limiter.limit("20/minute")
async def predict_match(request: Request, pred_req: MatchPredictionRequest) -> dict[str, Any]:
    """Predict match outcome for any two teams.

    Competition-agnostic: works for Premier League, Champions League,
    World Cup, or any competition. Combines team strength ratings,
    head-to-head history, and venue context.
    """
    from football_analytics.db import get_engine as _get_engine
    from football_analytics.prediction.match_predictor import MatchPredictor, VenueType

    engine = _get_engine()
    predictor = MatchPredictor(engine=engine, n_simulations=pred_req.n_simulations)

    try:
        venue = VenueType(pred_req.venue_type)
    except ValueError:
        venue = VenueType.NEUTRAL

    try:
        prediction = predictor.predict(
            team_a_id=pred_req.team_a_id,
            team_b_id=pred_req.team_b_id,
            competition_id=pred_req.competition_id,
            venue_type=venue,
        )
    except Exception as exc:
        logger.exception("Match prediction failed")
        raise HTTPException(status_code=500, detail=str(exc))

    # Serialise scoreline probabilities
    top_scores = sorted(prediction.scoreline_probabilities.items(), key=lambda x: x[1], reverse=True)[:15]

    return {
        "team_a": {"id": prediction.team_a_id, "name": prediction.team_a_name},
        "team_b": {"id": prediction.team_b_id, "name": prediction.team_b_name},
        "probabilities": {
            "team_a_win": prediction.team_a_win_prob,
            "draw": prediction.draw_prob,
            "team_b_win": prediction.team_b_win_prob,
        },
        "expected_goals": {
            "team_a": prediction.team_a_expected_xg,
            "team_b": prediction.team_b_expected_xg,
        },
        "most_likely_score": f"{prediction.most_likely_score[0]}-{prediction.most_likely_score[1]}",
        "markets": {
            "over_1_5": prediction.over_1_5_prob,
            "over_2_5": prediction.over_2_5_prob,
            "over_3_5": prediction.over_3_5_prob,
            "btts": prediction.btts_prob,
        },
        "scoreline_distribution": [{"score": f"{h}-{a}", "probability": prob} for (h, a), prob in top_scores],
        "confidence": prediction.confidence,
        "venue_type": prediction.venue_type,
        "n_simulations": prediction.n_simulations,
        "key_factors": [
            {
                "dimension": f.dimension,
                "description": f.description,
                "impact": f.impact,
            }
            for f in prediction.key_factors
        ],
        "head_to_head": (
            {
                "matches_played": prediction.head_to_head.matches_played,
                "team_a_wins": prediction.head_to_head.team_a_wins,
                "draws": prediction.head_to_head.draws,
                "team_b_wins": prediction.head_to_head.team_b_wins,
            }
            if prediction.head_to_head
            else None
        ),
        "model_version": prediction.model_version,
    }


@app.get("/api/v1/predict/ratings")
async def get_team_ratings(
    competition_id: int | None = Query(None, description="Filter by competition"),
    season_id: int | None = Query(None, description="Filter by season"),
) -> list[dict[str, Any]]:
    """Get current team strength ratings.

    Returns all rated teams sorted by overall rating, optionally
    filtered by competition.
    """
    from football_analytics.db import get_engine as _get_engine
    from football_analytics.prediction.team_rating import TeamRatingEngine

    engine = _get_engine()
    rating_engine = TeamRatingEngine(engine=engine)

    comp_ids = [competition_id] if competition_id else None
    season_ids = [season_id] if season_id else None
    ratings = rating_engine.compute_ratings(competition_ids=comp_ids, season_ids=season_ids)

    results = []
    for _tid, rating in sorted(ratings.items(), key=lambda x: x[1].overall_rating, reverse=True):
        results.append(
            {
                "team_id": rating.team_id,
                "team_name": rating.team_name,
                "overall_rating": rating.overall_rating,
                "offensive_strength": rating.offensive_strength,
                "defensive_strength": rating.defensive_strength,
                "pressing_intensity": rating.pressing_intensity,
                "possession_dominance": rating.possession_dominance,
                "set_piece_threat": rating.set_piece_threat,
                "directness": rating.directness,
                "form_trend": rating.form_trend,
                "matches_used": rating.matches_used,
                "confidence": rating.confidence,
            }
        )

    return results


@app.get("/api/v1/predict/matchup/{team_a_id}/{team_b_id}")
async def get_tactical_matchup(
    team_a_id: int,
    team_b_id: int,
    competition_id: int | None = Query(None),
    season_id: int | None = Query(None),
) -> dict[str, Any]:
    """Analyse tactical matchup between two teams.

    Compares team profiles across pressing, build-up, defensive shape,
    set pieces, and transitions. Returns advantage scores and
    coaching-friendly narrative.
    """
    from football_analytics.db import get_engine as _get_engine
    from football_analytics.prediction.tactical_matchup import analyse_matchup

    engine = _get_engine()
    matchup = analyse_matchup(
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        competition_id=competition_id,
        season_id=season_id,
        engine=engine,
    )

    return {
        "team_a": {"id": matchup.team_a_id, "name": matchup.team_a_name},
        "team_b": {"id": matchup.team_b_id, "name": matchup.team_b_name},
        "overall_advantage": matchup.overall_advantage,
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
        "tactical_narrative": matchup.tactical_narrative,
        "recommendations": matchup.recommendations,
        "matches_analysed": {
            "team_a": matchup.matches_analysed_a,
            "team_b": matchup.matches_analysed_b,
        },
    }


@app.post("/api/v1/predict/tournament")
@limiter.limit("5/minute")
async def simulate_tournament(request: Request, tourn_req: TournamentSimulationRequest) -> dict[str, Any]:
    """Simulate an entire tournament/competition.

    Supports any format: league (round-robin), groups+knockout (World Cup,
    Champions League), or straight knockout (FA Cup). Format is defined
    by the request parameters, not hardcoded.
    """
    from football_analytics.db import get_engine as _get_engine
    from football_analytics.prediction.team_rating import TeamRatingEngine
    from football_analytics.prediction.tournament import (
        CompetitionFormat,
        GroupConfig,
        TournamentFormat,
        TournamentSimulator,
    )

    engine = _get_engine()
    rating_engine = TeamRatingEngine(engine=engine)

    # Compute ratings for the competition context
    comp_ids = [tourn_req.competition_id] if tourn_req.competition_id else None
    ratings = rating_engine.compute_ratings(competition_ids=comp_ids)

    # Build tournament format from request
    fmt_type = CompetitionFormat(tourn_req.format_type)

    if fmt_type == CompetitionFormat.LEAGUE:
        if not tourn_req.team_ids:
            raise HTTPException(status_code=400, detail="team_ids required for league format")
        fmt = TournamentFormat.premier_league(tourn_req.team_ids)
    elif fmt_type == CompetitionFormat.GROUPS_KNOCKOUT:
        if not tourn_req.groups:
            raise HTTPException(status_code=400, detail="groups required for groups_knockout format")
        group_configs = [
            GroupConfig(
                group_name=g.get("group_name", f"Group {i + 1}"),
                team_ids=g["team_ids"],
                teams_advancing=g.get("teams_advancing", 2),
            )
            for i, g in enumerate(tourn_req.groups)
        ]
        fmt = TournamentFormat(
            format_type=fmt_type,
            name="Tournament",
            groups=group_configs,
            best_third_place_count=tourn_req.best_third_place_count,
            knockout_rounds=tourn_req.knockout_rounds,
            extra_time=True,
            penalties=True,
        )
    elif fmt_type == CompetitionFormat.KNOCKOUT:
        if not tourn_req.team_ids:
            raise HTTPException(status_code=400, detail="team_ids required for knockout format")
        fmt = TournamentFormat.knockout_cup(tourn_req.team_ids)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {tourn_req.format_type}")

    # Run simulation
    simulator = TournamentSimulator(ratings=ratings)
    result = simulator.simulate(fmt, n_simulations=tourn_req.n_simulations)

    # Serialise results
    team_results = []
    for _tid, tr in sorted(result.team_results.items(), key=lambda x: x[1].winner_prob, reverse=True):
        team_results.append(
            {
                "team_id": tr.team_id,
                "team_name": tr.team_name,
                "group_name": tr.group_name,
                "group_advance_prob": tr.group_advance_prob,
                "round_of_32_prob": tr.round_of_32_prob,
                "round_of_16_prob": tr.round_of_16_prob,
                "quarter_final_prob": tr.quarter_final_prob,
                "semi_final_prob": tr.semi_final_prob,
                "final_prob": tr.final_prob,
                "winner_prob": tr.winner_prob,
                # League metrics
                "expected_points": tr.expected_points,
                "expected_position": tr.expected_position,
                "title_prob": tr.title_prob,
                "top_4_prob": tr.top_4_prob,
                "relegation_prob": tr.relegation_prob,
            }
        )

    return {
        "tournament_name": result.tournament_name,
        "format_type": result.format_type,
        "n_simulations": result.n_simulations,
        "team_results": team_results,
    }


# ============================================================================
# Matchday Operations Endpoints
# ============================================================================


class FixtureCreateRequest(BaseModel):
    competition_id: int
    season_id: int
    match_date: str = Field(..., description="ISO date YYYY-MM-DD")
    kick_off: str | None = None
    home_team_id: int
    away_team_id: int
    venue_type: str = "home"
    stage: str = ""
    matchday: int = 0


class FixtureBatchCreateRequest(BaseModel):
    fixtures: list[FixtureCreateRequest]


class PreMatchRequest(BaseModel):
    our_team_id: int | None = None


class PostMatchRequest(BaseModel):
    match_id: int
    our_team_id: int | None = None


@app.get("/api/v1/matchday/fixtures")
def get_matchday_fixtures(
    competition_id: int | None = Query(None),
    status: str | None = Query(None),
    days_ahead: int = Query(14),
    team_id: int | None = Query(None),
) -> dict[str, Any]:
    """Get fixtures with optional filters."""
    from datetime import date, timedelta

    from football_analytics.matchday.fixtures import FixtureManager, FixtureStatus

    try:
        manager = FixtureManager()
        status_enum = FixtureStatus(status) if status else None
        fixtures = manager.get_fixtures(
            competition_id=competition_id,
            status=status_enum,
            from_date=date.today(),
            to_date=date.today() + timedelta(days=days_ahead),
            team_id=team_id,
        )
        return {
            "count": len(fixtures),
            "fixtures": [manager._fixture_to_dict(f) for f in fixtures],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/matchday/calendar")
def get_matchday_calendar(
    days_ahead: int = Query(14),
    days_behind: int = Query(7),
) -> dict[str, Any]:
    """Get calendar summary for the matchday dashboard."""
    from football_analytics.matchday.fixtures import FixtureManager

    try:
        manager = FixtureManager()
        return manager.get_calendar_summary(days_ahead=days_ahead, days_behind=days_behind)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/matchday/fixtures")
def create_fixture(request: FixtureCreateRequest) -> dict[str, Any]:
    """Create a new fixture."""
    from datetime import date as date_type

    from football_analytics.matchday.fixtures import Fixture, FixtureManager

    try:
        manager = FixtureManager()
        fixture = Fixture(
            competition_id=request.competition_id,
            season_id=request.season_id,
            match_date=date_type.fromisoformat(request.match_date),
            kick_off=request.kick_off,
            home_team_id=request.home_team_id,
            away_team_id=request.away_team_id,
            venue_type=request.venue_type,
            stage=request.stage,
            matchday=request.matchday,
        )
        fixture_id = manager.create_fixture(fixture)
        return {"fixture_id": fixture_id, "status": "created"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/matchday/fixtures/batch")
def create_fixtures_batch(request: FixtureBatchCreateRequest) -> dict[str, Any]:
    """Create multiple fixtures in a single request."""
    from datetime import date as date_type

    from football_analytics.matchday.fixtures import Fixture, FixtureManager

    try:
        manager = FixtureManager()
        fixtures = [
            Fixture(
                competition_id=f.competition_id,
                season_id=f.season_id,
                match_date=date_type.fromisoformat(f.match_date),
                kick_off=f.kick_off,
                home_team_id=f.home_team_id,
                away_team_id=f.away_team_id,
                venue_type=f.venue_type,
                stage=f.stage,
                matchday=f.matchday,
            )
            for f in request.fixtures
        ]
        ids = manager.create_fixtures_batch(fixtures)
        return {"fixture_ids": ids, "count": len(ids)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/api/v1/matchday/fixtures/{fixture_id}/status")
def update_fixture_status(
    fixture_id: int,
    status: str = Query(..., description="New status value"),
    match_id: int | None = Query(None),
) -> dict[str, Any]:
    """Update fixture lifecycle status."""
    from football_analytics.matchday.fixtures import FixtureManager, FixtureStatus

    try:
        status_enum = FixtureStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {[s.value for s in FixtureStatus]}",
        )

    try:
        manager = FixtureManager()
        manager.update_status(fixture_id, status_enum, match_id=match_id)
        return {"fixture_id": fixture_id, "status": status_enum.value}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/matchday/fixtures/{fixture_id}/pre-match")
def get_pre_match_pack(
    fixture_id: int,
    our_team_id: int | None = Query(None),
) -> dict[str, Any]:
    """Generate or retrieve pre-match intelligence pack."""
    from dataclasses import asdict

    from football_analytics.matchday.pre_match import generate_pre_match_pack

    try:
        pack = generate_pre_match_pack(
            fixture_id=fixture_id,
            our_team_id=our_team_id,
        )
        result = asdict(pack)
        # Serialise datetime
        result["generated_at"] = pack.generated_at.isoformat()
        if pack.match_date:
            result["match_date"] = pack.match_date.isoformat()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Pre-match pack generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/matchday/fixtures/{fixture_id}/post-match")
def generate_post_match(
    fixture_id: int,
    request: PostMatchRequest,
) -> dict[str, Any]:
    """Generate post-match review for a completed fixture."""
    from dataclasses import asdict

    from football_analytics.matchday.post_match import generate_post_match_review

    try:
        review = generate_post_match_review(
            match_id=request.match_id,
            our_team_id=request.our_team_id,
            fixture_id=fixture_id,
        )
        result = asdict(review)
        result["generated_at"] = review.generated_at.isoformat()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Post-match review generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/matchday/needing-preview")
def get_fixtures_needing_preview() -> dict[str, Any]:
    """Get fixtures that need pre-match packs (within 3 days, no pack yet)."""
    from football_analytics.matchday.fixtures import FixtureManager

    try:
        manager = FixtureManager()
        fixtures = manager.get_needing_preview()
        return {
            "count": len(fixtures),
            "fixtures": [manager._fixture_to_dict(f) for f in fixtures],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/matchday/needing-review")
def get_fixtures_needing_review() -> dict[str, Any]:
    """Get completed fixtures that haven't been reviewed."""
    from football_analytics.matchday.fixtures import FixtureManager

    try:
        manager = FixtureManager()
        fixtures = manager.get_needing_review()
        return {
            "count": len(fixtures),
            "fixtures": [manager._fixture_to_dict(f) for f in fixtures],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# Executive Intelligence Endpoints
# ============================================================================


class PlayerAssessmentRequest(BaseModel):
    player_id: int
    season_id: int | None = None


class CompetitionOutlookRequest(BaseModel):
    team_id: int
    competition_id: int
    season_id: int


class PostMatchSummaryRequest(BaseModel):
    match_id: int
    our_team_id: int | None = None


@app.get("/api/v1/executive/weekly-briefing")
def get_weekly_briefing(
    team_id: int = Query(...),
    season_id: int | None = Query(None),
) -> dict[str, Any]:
    """Generate weekly executive briefing."""
    from dataclasses import asdict

    from football_analytics.reports.executive import ExecutiveReportGenerator

    try:
        gen = ExecutiveReportGenerator()
        briefing = gen.weekly_briefing(team_id=team_id, season_id=season_id)
        result = asdict(briefing)
        result["generated_at"] = briefing.generated_at.isoformat()
        # Serialise enums
        result["week_difficulty"] = briefing.week_difficulty.value
        for m in result.get("squad_metrics", []):
            m["rag"] = m["rag"].value if hasattr(m.get("rag"), "value") else m["rag"]
            m["trend"] = m["trend"].value if hasattr(m.get("trend"), "value") else m["trend"]
        return result
    except Exception as exc:
        logger.exception("Weekly briefing generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/executive/player-assessment")
def get_player_assessment(request: PlayerAssessmentRequest) -> dict[str, Any]:
    """Generate executive player assessment."""
    from dataclasses import asdict

    from football_analytics.reports.executive import ExecutiveReportGenerator

    try:
        gen = ExecutiveReportGenerator()
        assessment = gen.player_assessment(player_id=request.player_id, season_id=request.season_id)
        result = asdict(assessment)
        result["trajectory"] = assessment.trajectory.value
        for k in result.get("kpis", []):
            k["rag"] = k["rag"].value if hasattr(k.get("rag"), "value") else k["rag"]
            k["trend"] = k["trend"].value if hasattr(k.get("trend"), "value") else k["trend"]
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/executive/competition-outlook")
def get_competition_outlook(request: CompetitionOutlookRequest) -> dict[str, Any]:
    """Generate competition campaign outlook."""
    from dataclasses import asdict

    from football_analytics.reports.executive import ExecutiveReportGenerator

    try:
        gen = ExecutiveReportGenerator()
        outlook = gen.competition_outlook(
            team_id=request.team_id,
            competition_id=request.competition_id,
            season_id=request.season_id,
        )
        result = asdict(outlook)
        result["form_rag"] = outlook.form_rag.value
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/executive/post-match-summary")
def get_post_match_executive_summary(
    request: PostMatchSummaryRequest,
) -> dict[str, Any]:
    """Generate one-page post-match executive summary."""
    from dataclasses import asdict

    from football_analytics.reports.executive import ExecutiveReportGenerator

    try:
        gen = ExecutiveReportGenerator()
        summary = gen.post_match_summary(match_id=request.match_id, our_team_id=request.our_team_id)
        result = asdict(summary)
        result["result_rag"] = summary.result_rag.value
        for m in result.get("key_metrics", []):
            m["rag"] = m["rag"].value if hasattr(m.get("rag"), "value") else m["rag"]
            m["trend"] = m["trend"].value if hasattr(m.get("trend"), "value") else m["trend"]
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# Ad-Hoc Analysis Endpoints
# ============================================================================


class QueryExecutionRequest(BaseModel):
    query_id: str
    parameters: dict[str, Any]


@app.get("/api/v1/analysis/queries")
def list_analysis_queries(
    category: str | None = Query(None),
) -> dict[str, Any]:
    """List available analytical queries."""
    from football_analytics.analysis.queries import AnalyticalQueryLibrary

    try:
        library = AnalyticalQueryLibrary()
        queries = library.list_queries(category=category)
        categories = library.get_categories()
        return {"categories": categories, "queries": queries, "count": len(queries)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/analysis/query")
def execute_analysis_query(request: QueryExecutionRequest) -> dict[str, Any]:
    """Execute a parameterised analytical query."""
    from football_analytics.analysis.queries import AnalyticalQueryLibrary

    try:
        library = AnalyticalQueryLibrary()
        results = library.execute_to_dict(request.query_id, request.parameters)
        return {
            "query_id": request.query_id,
            "parameters": request.parameters,
            "row_count": len(results),
            "results": results,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception(f"Query execution failed: {request.query_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# Cache & System Endpoints
# ============================================================================


@app.get("/api/v1/cache/stats")
def get_cache_stats():
    """Get Parquet cache statistics."""
    from football_analytics.cache import cache_stats

    return cache_stats()


class CacheInvalidateRequest(BaseModel):
    name: str | None = None


@app.post("/api/v1/cache/invalidate")
def invalidate_cache_endpoint(request: CacheInvalidateRequest):
    """Invalidate cache entries (all or by name prefix)."""
    from football_analytics.cache import invalidate_cache

    count = invalidate_cache(request.name)
    return {"invalidated": count}


@app.get("/api/v1/system/health/db")
def db_health_check():
    """Deep health check — verifies database connectivity."""
    try:
        from football_analytics.db import get_engine

        engine = get_engine()
        from sqlalchemy import text as sql_text

        with engine.connect() as conn:
            conn.execute(sql_text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unhealthy: {exc}")


@app.get("/api/v1/system/validation/{match_id}")
def validate_match(match_id: int):
    """Run data validation on a specific match."""
    from football_analytics.validation import DataValidator

    validator = DataValidator(log_to_db=False)
    report = validator.validate_match_events(match_id)
    return report.summary


def main() -> None:
    """Run the API server."""
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
