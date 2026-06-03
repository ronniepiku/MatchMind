"""Tests for executive intelligence reporting module."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from football_analytics.reports.executive import (
    CompetitionOutlook,
    ExecutiveReportGenerator,
    PlayerAssessment,
    PostMatchExecutiveSummary,
    RAGMetric,
    RAGStatus,
    TrendDirection,
    WeeklyBriefing,
)

# ─── RAGStatus Tests ──────────────────────────────────────────────────────────


class TestRAGStatus:
    """Tests for RAG traffic-light indicators."""

    def test_green_when_above_green_threshold(self):
        assert (
            RAGStatus.from_threshold(0.9, green_min=0.7, amber_min=0.4)
            == RAGStatus.GREEN
        )

    def test_green_at_exact_threshold(self):
        assert (
            RAGStatus.from_threshold(0.7, green_min=0.7, amber_min=0.4)
            == RAGStatus.GREEN
        )

    def test_amber_between_thresholds(self):
        assert (
            RAGStatus.from_threshold(0.5, green_min=0.7, amber_min=0.4)
            == RAGStatus.AMBER
        )

    def test_amber_at_exact_threshold(self):
        assert (
            RAGStatus.from_threshold(0.4, green_min=0.7, amber_min=0.4)
            == RAGStatus.AMBER
        )

    def test_red_below_amber_threshold(self):
        assert (
            RAGStatus.from_threshold(0.3, green_min=0.7, amber_min=0.4) == RAGStatus.RED
        )

    def test_red_for_zero_value(self):
        assert (
            RAGStatus.from_threshold(0.0, green_min=0.7, amber_min=0.4) == RAGStatus.RED
        )

    def test_enum_values(self):
        assert RAGStatus.RED.value == "red"
        assert RAGStatus.AMBER.value == "amber"
        assert RAGStatus.GREEN.value == "green"


# ─── TrendDirection Tests ──────────────────────────────────────────────────────


class TestTrendDirection:
    """Tests for trend direction enum."""

    def test_enum_values(self):
        assert TrendDirection.IMPROVING.value == "improving"
        assert TrendDirection.STABLE.value == "stable"
        assert TrendDirection.DECLINING.value == "declining"


# ─── Dataclass Tests ──────────────────────────────────────────────────────────


class TestDataclasses:
    """Tests for executive report data structures."""

    def test_rag_metric_defaults(self):
        metric = RAGMetric(name="Goals per 90", value=1.5, unit="goals")
        assert metric.rag == RAGStatus.GREEN
        assert metric.trend == TrendDirection.STABLE
        assert metric.context == ""

    def test_weekly_briefing_defaults(self):
        briefing = WeeklyBriefing()
        assert briefing.reporting_period == ""
        assert briefing.competitions == []
        assert briefing.squad_metrics == []
        assert briefing.upcoming_fixtures == []
        assert briefing.week_difficulty == RAGStatus.GREEN
        assert briefing.headline == ""

    def test_player_assessment_fields(self):
        assessment = PlayerAssessment(
            player_id=10,
            player_name="Test Player",
            position="Forward",
        )
        assert assessment.player_id == 10
        assert assessment.trajectory == TrendDirection.STABLE
        assert assessment.recommendation == ""
        assert assessment.kpis == []

    def test_competition_outlook_fields(self):
        outlook = CompetitionOutlook(
            competition_name="Premier League",
            season="2024/25",
            position=3,
            points=45,
            matches_played=20,
            matches_remaining=18,
        )
        assert outlook.position == 3
        assert outlook.points_vs_expected == 0.0
        assert outlook.targets == []
        assert outlook.form_rag == RAGStatus.GREEN

    def test_post_match_summary_fields(self):
        summary = PostMatchExecutiveSummary(
            match_date="2025-01-15",
            fixture="Arsenal 2-1 Chelsea",
            competition="Premier League",
            venue="Home",
        )
        assert summary.result_rag == RAGStatus.GREEN
        assert summary.key_metrics == []
        assert summary.summary_points == []


# ─── ExecutiveReportGenerator Tests ────────────────────────────────────────────


class TestExecutiveReportGenerator:
    """Tests for report generation (mocked DB)."""

    @pytest.fixture
    def mock_engine(self):
        return MagicMock()

    @pytest.fixture
    def generator(self, mock_engine):
        return ExecutiveReportGenerator(engine=mock_engine)

    def test_instantiation(self, generator):
        assert generator is not None
        assert generator._engine is not None

    @patch.object(ExecutiveReportGenerator, "_get_competition_standings")
    @patch.object(ExecutiveReportGenerator, "_get_squad_health")
    @patch.object(ExecutiveReportGenerator, "_get_upcoming_fixtures")
    @patch.object(ExecutiveReportGenerator, "_assess_difficulty")
    @patch.object(ExecutiveReportGenerator, "_generate_headline")
    @patch.object(ExecutiveReportGenerator, "_generate_recommendations")
    def test_weekly_briefing_structure(
        self,
        mock_recs,
        mock_headline,
        mock_difficulty,
        mock_upcoming,
        mock_squad,
        mock_standings,
        generator,
    ):
        mock_standings.return_value = [{"competition": "PL", "position": 3}]
        mock_squad.return_value = [RAGMetric(name="Fitness", value=85, unit="%")]
        mock_upcoming.return_value = [{"fixture": "vs Chelsea", "date": "2025-01-20"}]
        mock_difficulty.return_value = RAGStatus.AMBER
        mock_headline.return_value = ("Strong week ahead", ["Point 1"])
        mock_recs.return_value = ["Rest key players"]

        briefing = generator.weekly_briefing(team_id=1, season_id=90)

        assert isinstance(briefing, WeeklyBriefing)
        assert briefing.week_difficulty == RAGStatus.AMBER
        assert briefing.headline == "Strong week ahead"
        assert len(briefing.recommendations) == 1
        assert "reporting_period" in dir(briefing)

    @patch.object(ExecutiveReportGenerator, "_get_player_info")
    @patch.object(ExecutiveReportGenerator, "_get_player_season_stats")
    @patch.object(ExecutiveReportGenerator, "_compute_player_trend")
    @patch.object(ExecutiveReportGenerator, "_build_player_kpis")
    @patch.object(ExecutiveReportGenerator, "_derive_player_recommendation")
    def test_player_assessment_structure(
        self,
        mock_rec,
        mock_kpis,
        mock_trend,
        mock_stats,
        mock_info,
        generator,
    ):
        mock_info.return_value = {"player_name": "Test Player", "position": "Forward"}
        mock_stats.return_value = {"matches": 20, "goals": 10}
        mock_trend.return_value = {
            "direction": TrendDirection.IMPROVING,
            "narrative": "Strong form",
        }
        mock_kpis.return_value = [RAGMetric(name="Goals/90", value=0.5)]
        mock_rec.return_value = ("Extend", ["Consistent goal threat"])

        assessment = generator.player_assessment(player_id=42, season_id=90)

        assert isinstance(assessment, PlayerAssessment)
        assert assessment.player_name == "Test Player"
        assert assessment.trajectory == TrendDirection.IMPROVING
        assert assessment.recommendation == "Extend"
        assert assessment.confidence == "medium"
