"""Prediction engine endpoints — match prediction, ratings, tournament simulation, ML pipeline."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["prediction"])
logger = logging.getLogger(__name__)


# ─── Request Models ─────────────────────────────────────────────────────────


class MatchPredictionRequest(BaseModel):
    team_a_id: int = Field(..., description="First team ID")
    team_b_id: int = Field(..., description="Second team ID")
    competition_id: int | None = Field(None, description="Competition context for ratings")
    venue_type: str = Field("neutral", description="Venue: 'home', 'away', 'neutral'")
    n_simulations: int = Field(10000, ge=100, le=100000)


class TournamentSimulationRequest(BaseModel):
    competition_id: int = Field(..., description="Competition ID")
    format_type: str = Field(..., description="Format: 'league', 'groups_knockout', 'knockout'")
    groups: list[dict[str, Any]] | None = Field(None, description="Group configurations")
    team_ids: list[int] | None = Field(None, description="Team IDs (for league/knockout)")
    n_simulations: int = Field(10000, ge=100, le=100000)
    best_third_place_count: int = Field(0, ge=0)
    knockout_rounds: int = Field(0, ge=0)


class MLPredictionRequest(BaseModel):
    home_team_id: int = Field(..., gt=0)
    away_team_id: int = Field(..., gt=0)
    season_ids: list[int] | None = None


class MLTrainRequest(BaseModel):
    season_ids: list[int] | None = None


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/predict/match")
async def predict_match(request: Request, pred_req: MatchPredictionRequest) -> dict[str, Any]:
    """Predict match outcome for any two teams."""
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
            {"dimension": f.dimension, "description": f.description, "impact": f.impact} for f in prediction.key_factors
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


@router.get("/predict/ratings")
async def get_team_ratings(
    competition_id: int | None = Query(None),
    season_id: int | None = Query(None),
) -> list[dict[str, Any]]:
    """Get current team strength ratings."""
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


@router.get("/predict/matchup/{team_a_id}/{team_b_id}")
async def get_tactical_matchup(
    team_a_id: int,
    team_b_id: int,
    competition_id: int | None = Query(None),
    season_id: int | None = Query(None),
) -> dict[str, Any]:
    """Analyse tactical matchup between two teams."""
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
        "matches_analysed": {"team_a": matchup.matches_analysed_a, "team_b": matchup.matches_analysed_b},
    }


@router.post("/predict/tournament")
async def simulate_tournament(request: Request, tourn_req: TournamentSimulationRequest) -> dict[str, Any]:
    """Simulate an entire tournament/competition."""
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

    comp_ids = [tourn_req.competition_id] if tourn_req.competition_id else None
    ratings = rating_engine.compute_ratings(competition_ids=comp_ids)

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

    simulator = TournamentSimulator(ratings=ratings)
    result = simulator.simulate(fmt, n_simulations=tourn_req.n_simulations)

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


# ─── ML Prediction ─────────────────────────────────────────────────────────


@router.post("/predict/ml")
async def ml_predict_match(request: Request, pred_req: MLPredictionRequest) -> dict[str, Any]:
    """Predict match outcome using gradient-boosted ML model."""
    from football_analytics.prediction.ml_pipeline import MLMatchPredictor

    predictor = MLMatchPredictor()
    if not predictor.load():
        raise HTTPException(status_code=503, detail="ML model not trained. Call POST /predict/ml/train first.")

    try:
        prediction = predictor.predict(
            home_team_id=pred_req.home_team_id,
            away_team_id=pred_req.away_team_id,
            season_ids=pred_req.season_ids,
        )
    except Exception:
        logger.exception("ML prediction failed")
        raise HTTPException(status_code=500, detail="Internal server error")

    return {
        "home_team": {"id": prediction.home_team_id, "name": prediction.home_team_name},
        "away_team": {"id": prediction.away_team_id, "name": prediction.away_team_name},
        "probabilities": {
            "home_win": prediction.home_win_prob,
            "draw": prediction.draw_prob,
            "away_win": prediction.away_win_prob,
        },
        "predicted_outcome": prediction.predicted_outcome,
        "confidence": prediction.confidence,
        "expected_goals": prediction.expected_goals if hasattr(prediction, "expected_goals") else {},
        "most_likely_score": prediction.most_likely_score if hasattr(prediction, "most_likely_score") else "",
        "markets": prediction.markets if hasattr(prediction, "markets") else {},
        "feature_contributions": prediction.feature_contributions,
        "model_version": prediction.model_version,
    }


@router.post("/predict/ml/train")
async def ml_train_model(request: Request, train_req: MLTrainRequest) -> dict[str, Any]:
    """Train the ML prediction model on historical data."""
    from football_analytics.prediction.ml_pipeline import ML_MODEL_VERSION, MLMatchPredictor

    predictor = MLMatchPredictor()

    try:
        metrics = predictor.train(season_ids=train_req.season_ids)
        predictor.save()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("ML model training failed")
        raise HTTPException(status_code=500, detail="Internal server error")

    return {
        "status": "trained",
        "model_version": ML_MODEL_VERSION,
        "metrics": {
            "brier_score": metrics.brier_score,
            "log_loss": metrics.log_loss,
            "roc_auc_home": metrics.roc_auc_home,
            "roc_auc_draw": metrics.roc_auc_draw,
            "roc_auc_away": metrics.roc_auc_away,
            "accuracy": metrics.accuracy,
            "calibration_error": metrics.calibration_error,
            "n_matches": metrics.n_matches,
        },
        "top_features": metrics.feature_importance,
    }


@router.get("/predict/ml/status")
async def ml_model_status() -> dict[str, Any]:
    """Check ML model status."""
    from football_analytics.prediction.ml_pipeline import ML_MODEL_VERSION, MLMatchPredictor, _get_models_dir

    predictor = MLMatchPredictor()
    model_loaded = predictor.load()
    metrics = predictor.get_metrics()

    return {
        "model_available": model_loaded,
        "model_version": ML_MODEL_VERSION,
        "model_path": str(_get_models_dir() / f"ml_predictor_v{ML_MODEL_VERSION}.pkl"),
        "metrics": (
            {
                "brier_score": metrics.brier_score,
                "log_loss": metrics.log_loss,
                "accuracy": metrics.accuracy,
                "n_matches": metrics.n_matches,
            }
            if metrics
            else None
        ),
    }
