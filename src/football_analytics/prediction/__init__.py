"""Prediction package — competition-agnostic match and tournament forecasting.

Modules:
    team_rating       — Time-weighted team strength rating system
    match_predictor   — Match outcome prediction service
    tournament        — Format-agnostic tournament simulation engine
    tactical_matchup  — Tactical matchup analysis between teams
"""

from football_analytics.prediction.match_predictor import MatchPredictor
from football_analytics.prediction.tactical_matchup import analyse_matchup
from football_analytics.prediction.team_rating import TeamRating, TeamRatingEngine
from football_analytics.prediction.tournament import TournamentSimulator

__all__ = [
    "MatchPredictor",
    "TeamRating",
    "TeamRatingEngine",
    "TournamentSimulator",
    "analyse_matchup",
]
