"""Matchday operations package — calendar-driven pre/post-match analysis workflows.

Modules:
    fixtures    — Multi-competition fixture management and lifecycle
    pre_match   — Automated pre-match intelligence pack generation
    post_match  — Post-match performance review engine
    reviews     — Structured longitudinal performance reviews
"""

from football_analytics.matchday.fixtures import Fixture, FixtureManager, FixtureStatus
from football_analytics.matchday.post_match import (
    PostMatchReview,
    generate_post_match_review,
)
from football_analytics.matchday.pre_match import PreMatchPack, generate_pre_match_pack
from football_analytics.matchday.reviews import (
    CompetitionReview,
    OpponentDossier,
    PlayerReview,
    UnitReview,
    generate_competition_review,
    generate_opponent_dossier,
    generate_player_review,
)

__all__ = [
    "CompetitionReview",
    "Fixture",
    "FixtureManager",
    "FixtureStatus",
    "OpponentDossier",
    "PlayerReview",
    "PostMatchReview",
    "PreMatchPack",
    "UnitReview",
    "generate_competition_review",
    "generate_opponent_dossier",
    "generate_player_review",
    "generate_post_match_review",
    "generate_pre_match_pack",
]
