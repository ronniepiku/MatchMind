"""Prediction package — competition-agnostic match and tournament forecasting.

Modules:
    team_rating       — Time-weighted team strength rating system
    match_predictor   — Match outcome prediction service
    tournament        — Format-agnostic tournament simulation engine
    tactical_matchup  — Tactical matchup analysis between teams
    ml_pipeline       — Gradient-boosted ML match prediction with feature engineering
"""

from football_analytics.prediction.match_predictor import MatchPredictor
from football_analytics.prediction.ml_pipeline import (
    ML_MODEL_VERSION,
    MatchFeatureEngine,
    MLMatchPredictor,
    MLPrediction,
)
from football_analytics.prediction.tactical_matchup import analyse_matchup
from football_analytics.prediction.team_rating import TeamRating, TeamRatingEngine
from football_analytics.prediction.tournament import TournamentSimulator

# Canonical prediction model version — re-exported from ml_pipeline
PREDICTION_MODEL_VERSION = ML_MODEL_VERSION

__all__ = [
    "ML_MODEL_VERSION",
    "MatchFeatureEngine",
    "MatchPredictor",
    "MLMatchPredictor",
    "MLPrediction",
    "PREDICTION_MODEL_VERSION",
    "TeamRating",
    "TeamRatingEngine",
    "TournamentSimulator",
    "analyse_matchup",
]
