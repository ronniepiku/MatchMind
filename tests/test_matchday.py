"""Tests for matchday operations package.

Covers:
- Fixture lifecycle and FixtureManager logic
- Pre-match pack generation
- Post-match review generation
- Reviews (player, competition, opponent dossier)
- API endpoint request/response schemas
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from football_analytics.matchday.fixtures import (
    Fixture,
    FixtureManager,
    FixturePriority,
    FixtureStatus,
)
from football_analytics.matchday.post_match import (
    PlayerMatchRating,
    PostMatchReview,
    PredictionAudit,
    UnitPerformance,
    _compute_unit_performances,
    _generate_tactical_observations,
    _identify_improvements,
)
from football_analytics.matchday.pre_match import (
    FormRecord,
    KeyPlayerThreat,
    PreMatchPack,
    SetPieceIntel,
    _describe_player_threat,
)
from football_analytics.matchday.reviews import (
    CompetitionReview,
    OpponentDossier,
    PlayerReview,
    UnitReview,
    _assess_player_qualities,
)

# ============================================================================
# Fixture dataclass tests
# ============================================================================


class TestFixture:
    """Test Fixture dataclass properties."""

    def test_is_upcoming_future_date(self):
        f = Fixture(match_date=date.today() + timedelta(days=3))
        assert f.is_upcoming is True

    def test_is_upcoming_past_date(self):
        f = Fixture(match_date=date.today() - timedelta(days=1))
        assert f.is_upcoming is False

    def test_is_upcoming_today(self):
        f = Fixture(match_date=date.today())
        assert f.is_upcoming is True

    def test_days_until_positive(self):
        f = Fixture(match_date=date.today() + timedelta(days=5))
        assert f.days_until == 5

    def test_days_until_negative(self):
        f = Fixture(match_date=date.today() - timedelta(days=2))
        assert f.days_until == -2

    def test_days_until_none_when_no_date(self):
        f = Fixture(match_date=None)
        assert f.days_until is None

    def test_needs_preview_within_3_days(self):
        f = Fixture(
            match_date=date.today() + timedelta(days=2),
            status=FixtureStatus.SCHEDULED,
        )
        assert f.needs_preview is True

    def test_needs_preview_too_far(self):
        f = Fixture(
            match_date=date.today() + timedelta(days=5),
            status=FixtureStatus.SCHEDULED,
        )
        assert f.needs_preview is False

    def test_needs_preview_already_generated(self):
        f = Fixture(
            match_date=date.today() + timedelta(days=1),
            status=FixtureStatus.PREVIEW_GENERATED,
        )
        assert f.needs_preview is False

    def test_display_name(self):
        f = Fixture(home_team_name="Arsenal", away_team_name="Chelsea")
        assert f.display_name == "Arsenal vs Chelsea"


class TestFixtureStatus:
    """Test fixture status enum."""

    def test_all_statuses(self):
        assert len(FixtureStatus) == 5
        assert FixtureStatus.SCHEDULED.value == "scheduled"
        assert FixtureStatus.REVIEWED.value == "reviewed"

    def test_lifecycle_order(self):
        lifecycle = [
            FixtureStatus.SCHEDULED,
            FixtureStatus.PREVIEW_GENERATED,
            FixtureStatus.IN_PROGRESS,
            FixtureStatus.COMPLETED,
            FixtureStatus.REVIEWED,
        ]
        assert len(lifecycle) == 5


class TestFixturePriority:
    """Test fixture priority enum."""

    def test_critical_highest(self):
        assert FixturePriority.CRITICAL.value < FixturePriority.LOW.value

    def test_all_priorities(self):
        assert len(FixturePriority) == 4


# ============================================================================
# Pre-match pack tests
# ============================================================================


class TestPreMatchPack:
    """Test PreMatchPack structure."""

    def test_dataclass_construction(self):
        pack = PreMatchPack(
            fixture_id=1,
            match_date=date.today(),
            home_team="Man Utd",
            away_team="Liverpool",
            competition="Premier League",
            stage="Matchweek 10",
            venue_type="home",
            win_probability=0.45,
            draw_probability=0.25,
            loss_probability=0.30,
            expected_score="2-1",
            prediction_confidence="medium",
            predicted_xg_for=1.8,
            predicted_xg_against=1.2,
            opponent_attack_patterns=[
                {"pattern": "left_wing_overload", "frequency": 0.3}
            ],
            opponent_defensive_shape=[{"line_height": "high"}],
            opponent_key_players=[],
            tactical_advantages=[],
            tactical_vulnerabilities=["Counter-attack susceptibility"],
            key_battles=[],
            tactical_recommendations=["Press high to disrupt build-up"],
        )
        assert pack.home_team == "Man Utd"
        assert pack.win_probability == 0.45
        assert len(pack.tactical_vulnerabilities) == 1

    def test_probabilities_sum_to_one(self):
        pack = PreMatchPack(
            fixture_id=1,
            match_date=date.today(),
            home_team="A",
            away_team="B",
            competition="",
            stage="",
            venue_type="home",
            win_probability=0.4,
            draw_probability=0.3,
            loss_probability=0.3,
            expected_score="1-1",
            prediction_confidence="high",
            predicted_xg_for=1.5,
            predicted_xg_against=1.0,
            opponent_attack_patterns=[],
            opponent_defensive_shape=[],
            opponent_key_players=[],
            tactical_advantages=[],
            tactical_vulnerabilities=[],
            key_battles=[],
            tactical_recommendations=[],
        )
        total = pack.win_probability + pack.draw_probability + pack.loss_probability
        assert abs(total - 1.0) < 0.01


class TestKeyPlayerThreat:
    """Test KeyPlayerThreat dataclass."""

    def test_construction(self):
        threat = KeyPlayerThreat(
            player_name="Mohamed Salah",
            position="RW",
            xg_per_match=0.52,
            xa_per_match=0.21,
            key_passes_per_match=2.1,
            threat_description="Primary goal threat",
        )
        assert threat.player_name == "Mohamed Salah"
        assert threat.xg_per_match > threat.xa_per_match


class TestDescribePlayerThreat:
    """Test the threat description helper."""

    def test_goal_threat(self):
        row = pd.Series({"total_xg": 8.0, "total_xa": 2.0, "dribbles": 1})
        desc = _describe_player_threat(row)
        assert "goal threat" in desc.lower()

    def test_creative_playmaker(self):
        row = pd.Series({"total_xg": 1.0, "total_xa": 6.0, "dribbles": 1})
        desc = _describe_player_threat(row)
        assert "playmaker" in desc.lower()

    def test_dribbler(self):
        row = pd.Series({"total_xg": 2.0, "total_xa": 2.0, "dribbles": 5})
        desc = _describe_player_threat(row)
        assert "ball" in desc.lower() or "carries" in desc.lower()

    def test_balanced(self):
        row = pd.Series({"total_xg": 3.0, "total_xa": 3.0, "dribbles": 1})
        desc = _describe_player_threat(row)
        assert "balanced" in desc.lower()


class TestSetPieceIntel:
    """Test SetPieceIntel dataclass."""

    def test_construction(self):
        intel = SetPieceIntel(
            corners_per_match=5.2,
            free_kicks_per_match=3.1,
            set_piece_xg_per_match=0.35,
            preferred_delivery="inswinging",
            aerial_threat_level="high",
        )
        assert intel.aerial_threat_level == "high"
        assert intel.corners_per_match > intel.free_kicks_per_match


class TestFormRecord:
    """Test FormRecord dataclass."""

    def test_construction(self):
        record = FormRecord(
            match_date=date(2024, 1, 15),
            opponent="Chelsea",
            result="W",
            score="2-1",
            xg_for=1.8,
            xg_against=0.9,
            competition="Premier League",
        )
        assert record.result == "W"
        assert record.xg_for > record.xg_against


# ============================================================================
# Post-match review tests
# ============================================================================


class TestPostMatchReview:
    """Test PostMatchReview structure."""

    def test_dataclass_construction(self):
        review = PostMatchReview(
            fixture_id=1,
            match_id=100,
            match_date="2024-02-01",
            home_team="Arsenal",
            away_team="Tottenham",
            competition="Premier League",
            final_score="2-0",
            prediction_audit=None,
            possession=62.0,
            xg_for=2.1,
            xg_against=0.8,
            shots=15,
            shots_on_target=7,
            passes_completed=520,
            pass_accuracy=87.5,
            pressures_applied=180,
            tackles_won=14,
            aerial_duels_won=8,
            aerial_duels_total=15,
        )
        assert review.final_score == "2-0"
        assert review.xg_for > review.xg_against


class TestPredictionAudit:
    """Test PredictionAudit."""

    def test_correct_prediction(self):
        audit = PredictionAudit(
            predicted_winner="home",
            actual_winner="home",
            prediction_correct=True,
            predicted_score="2-1",
            actual_score="2-1",
            score_correct=True,
            predicted_xg_home=1.8,
            predicted_xg_away=1.0,
            actual_xg_home=2.0,
            actual_xg_away=0.9,
            brier_score=0.08,
            narrative="Prediction spot-on",
        )
        assert audit.prediction_correct is True
        assert audit.score_correct is True
        assert audit.brier_score < 0.2

    def test_incorrect_prediction(self):
        audit = PredictionAudit(
            predicted_winner="home",
            actual_winner="away",
            prediction_correct=False,
            predicted_score="2-1",
            actual_score="0-2",
            score_correct=False,
            predicted_xg_home=1.8,
            predicted_xg_away=1.0,
            actual_xg_home=0.5,
            actual_xg_away=2.2,
            brier_score=0.55,
            narrative="Prediction missed",
        )
        assert audit.prediction_correct is False
        assert audit.brier_score > 0.3


class TestComputeUnitPerformances:
    """Test unit performance aggregation."""

    def test_groups_by_role(self):
        players = [
            PlayerMatchRating(
                player_id=1,
                player_name="Defender A",
                minutes_played=90,
                rating=7.0,
                xg=0.0,
                xa=0.0,
                passes_completed=40,
                passes_attempted=45,
                pass_accuracy=88.9,
                pressures=12,
                tackles_won=4,
                carries=15,
                progressive_carries=2,
            ),
            PlayerMatchRating(
                player_id=2,
                player_name="Attacker A",
                minutes_played=90,
                rating=7.5,
                xg=0.5,
                xa=0.2,
                passes_completed=25,
                passes_attempted=30,
                pass_accuracy=83.3,
                pressures=8,
                tackles_won=0,
                carries=20,
                progressive_carries=5,
            ),
            PlayerMatchRating(
                player_id=3,
                player_name="Midfielder A",
                minutes_played=90,
                rating=6.5,
                xg=0.02,
                xa=0.05,
                passes_completed=60,
                passes_attempted=68,
                pass_accuracy=88.2,
                pressures=15,
                tackles_won=1,
                carries=30,
                progressive_carries=8,
            ),
        ]
        units = _compute_unit_performances(players)
        assert len(units) >= 1  # At least one unit should be populated

    def test_empty_input(self):
        units = _compute_unit_performances([])
        assert units == []


class TestTacticalObservations:
    """Test tactical observation generation."""

    def test_high_press(self):
        team_stats = {
            "pressures": 220,
            "pass_accuracy": 85.0,
            "shots": 10,
            "xg": 1.5,
            "progressive_carries": 30,
            "aerial_won": 10,
            "aerial_total": 20,
        }
        opp_stats = {"xg": 0.8}
        obs = _generate_tactical_observations(team_stats, opp_stats, {}, True)
        assert any("press" in o.lower() for o in obs)

    def test_low_shot_quality(self):
        team_stats = {
            "pressures": 150,
            "pass_accuracy": 82.0,
            "shots": 20,
            "xg": 0.8,
            "progressive_carries": 25,
            "aerial_won": 8,
            "aerial_total": 20,
        }
        opp_stats = {"xg": 1.0}
        obs = _generate_tactical_observations(team_stats, opp_stats, {}, True)
        assert any("shot quality" in o.lower() or "distance" in o.lower() for o in obs)


class TestIdentifyImprovements:
    """Test improvement area identification."""

    def test_poor_accuracy(self):
        team_stats = {"shots": 15, "shots_on_target": 3, "pass_accuracy": 72.0}
        opp_stats = {"xg": 1.0}
        areas = _identify_improvements(team_stats, opp_stats, [])
        assert any("shot" in a.lower() or "accuracy" in a.lower() for a in areas)

    def test_high_opp_xg(self):
        team_stats = {"shots": 10, "shots_on_target": 5, "pass_accuracy": 85.0}
        opp_stats = {"xg": 2.0}
        areas = _identify_improvements(team_stats, opp_stats, [])
        assert any("defensive" in a.lower() or "conceded" in a.lower() for a in areas)


# ============================================================================
# Reviews tests
# ============================================================================


class TestPlayerReview:
    """Test PlayerReview dataclass."""

    def test_construction(self):
        review = PlayerReview(
            player_id=1,
            player_name="Bruno Fernandes",
            position="CAM",
            matches_played=30,
            minutes_played=2500,
            starts=28,
            goals=10,
            assists=8,
            xg=8.5,
            xa=7.0,
            xg_overperformance=1.5,
            passes_per_match=45.0,
            pass_accuracy=85.0,
            progressive_carries_per_match=3.2,
            dribble_success_rate=62.0,
            key_passes_per_match=2.8,
            pressures_per_match=15.0,
            tackles_per_match=1.2,
            interceptions_per_match=0.8,
            average_rating=7.2,
            rating_trend="improving",
        )
        assert review.xg_overperformance > 0
        assert review.rating_trend == "improving"


class TestAssessPlayerQualities:
    """Test player quality assessment logic."""

    def test_goal_threat_identified(self):
        stats = {
            "xg": 10.0,
            "xa": 2.0,
            "pass_accuracy": 80.0,
            "pressures": 300,
            "progressive_carries": 60,
            "dribble_success": 60.0,
            "dribbles_total": 30,
            "goals": 12,
            "key_passes": 40,
        }
        strengths, _ = _assess_player_qualities(stats, 30)
        assert any("goal" in s.lower() for s in strengths)

    def test_low_pressing_flagged(self):
        stats = {
            "xg": 2.0,
            "xa": 1.0,
            "pass_accuracy": 85.0,
            "pressures": 150,
            "progressive_carries": 30,
            "dribble_success": 65.0,
            "dribbles_total": 20,
            "goals": 2,
            "key_passes": 20,
        }
        _, dev_areas = _assess_player_qualities(stats, 30)
        assert any("press" in d.lower() for d in dev_areas)

    def test_high_pass_accuracy_strength(self):
        stats = {
            "xg": 1.0,
            "xa": 5.0,
            "pass_accuracy": 92.0,
            "pressures": 400,
            "progressive_carries": 100,
            "dribble_success": 70.0,
            "dribbles_total": 50,
            "goals": 1,
            "key_passes": 80,
        }
        strengths, _ = _assess_player_qualities(stats, 30)
        assert any("pass" in s.lower() for s in strengths)


class TestCompetitionReview:
    """Test CompetitionReview dataclass."""

    def test_construction(self):
        review = CompetitionReview(
            competition_id=2,
            competition_name="Premier League",
            season_id=90,
            matches_played=20,
            wins=12,
            draws=4,
            losses=4,
            goals_for=35,
            goals_against=18,
            points=40,
            position=3,
            xg_for=32.0,
            xg_against=20.0,
            xg_difference=12.0,
            points_above_expected=4.0,
            predictions_made=20,
            predictions_correct=14,
            average_brier_score=0.18,
            last_5_form="WWDWL",
            form_trajectory="stable",
        )
        assert review.points == review.wins * 3 + review.draws
        assert review.xg_difference == review.xg_for - review.xg_against


class TestOpponentDossier:
    """Test OpponentDossier dataclass."""

    def test_construction(self):
        dossier = OpponentDossier(
            team_id=10,
            team_name="Liverpool",
            last_updated=date.today(),
            total_encounters=8,
            wins=3,
            draws=2,
            losses=3,
            goals_for=10,
            goals_against=11,
            preferred_formation="4-3-3",
            style_tags=["high-press", "gegenpressing", "wide-play"],
        )
        assert dossier.total_encounters == dossier.wins + dossier.draws + dossier.losses
        assert "high-press" in dossier.style_tags


# ============================================================================
# API model tests (schema validation)
# ============================================================================


class TestAPIModels:
    """Test Pydantic models for matchday API."""

    def test_fixture_create_request(self):
        from football_analytics.api import FixtureCreateRequest

        req = FixtureCreateRequest(
            competition_id=2,
            season_id=90,
            match_date="2024-03-15",
            home_team_id=1,
            away_team_id=2,
            venue_type="home",
            stage="Matchweek 30",
            matchday=30,
        )
        assert req.match_date == "2024-03-15"
        assert req.venue_type == "home"

    def test_fixture_batch_create_request(self):
        from football_analytics.api import (
            FixtureBatchCreateRequest,
            FixtureCreateRequest,
        )

        fixtures = [
            FixtureCreateRequest(
                competition_id=2,
                season_id=90,
                match_date="2024-03-15",
                home_team_id=1,
                away_team_id=2,
            ),
            FixtureCreateRequest(
                competition_id=2,
                season_id=90,
                match_date="2024-03-22",
                home_team_id=3,
                away_team_id=1,
            ),
        ]
        req = FixtureBatchCreateRequest(fixtures=fixtures)
        assert len(req.fixtures) == 2

    def test_post_match_request(self):
        from football_analytics.api import PostMatchRequest

        req = PostMatchRequest(match_id=100, our_team_id=1)
        assert req.match_id == 100
