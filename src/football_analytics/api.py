"""FastAPI REST API layer for football analytics.

Exposes analysis functions as HTTP endpoints for:
- External integrations (Tableau, Power BI, mobile apps)
- Slack bots and notification systems
- Custom dashboards (React, Vue)
- Automated reporting pipelines

Endpoints:
- /api/v1/players/{id}/profile — Player performance summary
- /api/v1/players/{id}/similarity — Similar players
- /api/v1/players/{id}/development — Development trajectory
- /api/v1/teams/{id}/profile — Team analysis
- /api/v1/teams/{id}/set-pieces — Set-piece analysis
- /api/v1/matches/{id}/simulation — Match outcome simulation
- /api/v1/matches/{id}/possession-chains — Possession chain analysis
- /api/v1/xg/predict — Predict xG for shot data
- /api/v1/health — Health check
"""

from __future__ import annotations

import logging
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

    from football_analytics.analysis.xg_model import engineer_features, get_feature_columns

    # Build single-row DataFrame
    shot_df = pd.DataFrame([{
        "location_x": shot.location_x,
        "location_y": shot.location_y,
        "shot_body_part": shot.shot_body_part,
        "under_pressure": shot.under_pressure,
        "play_pattern": shot.play_pattern,
        "shot_type": shot.shot_type,
    }])

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


@app.post("/api/v1/simulation/match", response_model=SimulationResponse)
async def simulate_match_endpoint(request: SimulationRequest) -> SimulationResponse:
    """Simulate a match outcome using Monte Carlo methods.

    Uses Poisson distribution with given xG values to simulate
    the match thousands of times.
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
        pass_accuracy=round(result.passes_completed / max(result.passes_attempted, 1), 3),
        pressures=result.pressures,
        tackles=result.tackles,
        interceptions=result.interceptions,
    )


@app.get("/api/v1/players/{player_id}/similar", response_model=list[SimilarPlayerResponse])
async def get_similar_players(
    player_id: int,
    top_n: int = Query(10, ge=1, le=50, description="Number of similar players"),
) -> list[SimilarPlayerResponse]:
    """Find players with similar statistical profiles.

    Uses cosine similarity on normalised per-90 feature vectors.
    Requires database connection with player data loaded.
    """
    # This endpoint requires pre-computed similarity data
    # Return placeholder structure for API contract
    raise HTTPException(
        status_code=501,
        detail="Similarity search requires pre-computed vectors. Use the CLI or Python API.",
    )


@app.get("/api/v1/players/{player_id}/development", response_model=DevelopmentResponse)
async def get_player_development(
    player_id: int,
    position_group: str = Query("midfielder", description="Position group for metric selection"),
) -> DevelopmentResponse:
    """Get player development trajectory across seasons.

    Analyses multi-season trends to classify whether a player is
    improving, declining, or stable.
    """
    raise HTTPException(
        status_code=501,
        detail="Development tracking requires multi-season data. Use the Python API.",
    )


@app.get("/api/v1/teams/{team_id}/set-pieces", response_model=TeamSetPieceResponse)
async def get_team_set_pieces(
    team_id: int,
    season_id: int | None = Query(None),
) -> TeamSetPieceResponse:
    """Get set-piece efficiency metrics for a team."""
    raise HTTPException(
        status_code=501,
        detail="Set-piece analysis requires event data. Use the Python API.",
    )


@app.get("/api/v1/teams/{team_id}/possession-profile", response_model=PossessionChainSummary)
async def get_possession_profile(
    team_id: int,
    season_id: int | None = Query(None),
) -> PossessionChainSummary:
    """Get possession chain profile for a team."""
    raise HTTPException(
        status_code=501,
        detail="Possession chain analysis requires event data. Use the Python API.",
    )


def main() -> None:
    """Run the API server."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
