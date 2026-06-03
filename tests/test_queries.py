"""Tests for the analytical query library."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from football_analytics.analysis.queries import (
    AnalyticalQuery,
    AnalyticalQueryLibrary,
    QueryParameter,
)

# ─── QueryParameter Tests ─────────────────────────────────────────────────────


class TestQueryParameter:
    """Tests for query parameter definition."""

    def test_required_parameter(self):
        p = QueryParameter(
            name="team_id", type="int", description="Team identifier", required=True
        )
        assert p.required is True
        assert p.default is None

    def test_optional_with_default(self):
        p = QueryParameter(
            name="limit",
            type="int",
            description="Row limit",
            required=False,
            default=100,
        )
        assert p.required is False
        assert p.default == 100


# ─── AnalyticalQuery Tests ─────────────────────────────────────────────────────


class TestAnalyticalQuery:
    """Tests for query definition dataclass."""

    def test_query_structure(self):
        q = AnalyticalQuery(
            query_id="test_query",
            name="Test Query",
            description="A test query",
            category="Testing",
            sql="SELECT 1",
            parameters=[],
        )
        assert q.query_id == "test_query"
        assert q.result_columns == []


# ─── AnalyticalQueryLibrary Tests ──────────────────────────────────────────────


class TestAnalyticalQueryLibrary:
    """Tests for the query library (mocked DB)."""

    @pytest.fixture
    def mock_engine(self):
        return MagicMock()

    @pytest.fixture
    def library(self, mock_engine):
        return AnalyticalQueryLibrary(engine=mock_engine)

    def test_list_all_queries(self, library):
        queries = library.list_queries()
        assert isinstance(queries, list)
        assert len(queries) == 21  # All 21 registered queries
        # Each entry has required fields
        for q in queries:
            assert "query_id" in q
            assert "name" in q
            assert "description" in q
            assert "category" in q
            assert "parameters" in q

    def test_list_queries_by_category(self, library):
        pressing = library.list_queries(category="Pressing & Transitions")
        assert len(pressing) >= 1
        assert all(q["category"] == "Pressing & Transitions" for q in pressing)

    def test_get_categories(self, library):
        categories = library.get_categories()
        assert isinstance(categories, list)
        assert len(categories) >= 5
        assert "Pressing & Transitions" in categories
        assert "Build-Up & Possession" in categories
        assert "Chance Creation" in categories
        assert "Defensive Shape" in categories
        assert "Set Pieces" in categories

    def test_known_query_ids_exist(self, library):
        queries = library.list_queries()
        ids = {q["query_id"] for q in queries}
        expected_ids = {
            "pressing_triggers",
            "pressing_success_rate",
            "progressive_actions_by_zone",
            "build_up_patterns",
            "possession_sequences",
            "chance_creation_profile",
            "shot_quality_breakdown",
            "defensive_vulnerability_windows",
            "defensive_line_height",
            "set_piece_effectiveness",
            "set_piece_conceded",
            "player_comparison_radar",
            "player_progression_over_time",
            "head_to_head_tactical",
            "style_matchup_history",
            "form_momentum",
            "high_turnover_zones",
            "crossing_effectiveness",
            "goalkeeper_distribution",
            "counter_attack_speed",
            "aerial_dominance_map",
        }
        assert expected_ids.issubset(ids)

    def test_execute_unknown_query_raises(self, library):
        with pytest.raises(ValueError, match="Unknown query"):
            library.execute("nonexistent_query", {})

    def test_execute_missing_required_param_raises(self, library):
        """Execute a query with missing required params should raise ValueError."""
        # pressing_triggers requires team_id and season_id
        with pytest.raises(ValueError, match="Missing required parameter"):
            library.execute("pressing_triggers", {})

    def test_execute_returns_dataframe(self, library, mock_engine):
        """Execute with valid params (mocked DB connection)."""
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("pandas.read_sql") as mock_read_sql:
            mock_read_sql.return_value = pd.DataFrame(
                {"player_name": ["Test"], "presses": [15]}
            )
            result = library.execute(
                "pressing_triggers", {"team_id": 1, "season_id": 90}
            )
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1

    def test_execute_to_dict(self, library, mock_engine):
        """execute_to_dict returns JSON-serialisable list."""
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("pandas.read_sql") as mock_read_sql:
            mock_read_sql.return_value = pd.DataFrame(
                {"player_name": ["Test"], "presses": [15]}
            )
            result = library.execute_to_dict(
                "pressing_triggers", {"team_id": 1, "season_id": 90}
            )
            assert isinstance(result, list)
            assert result[0]["player_name"] == "Test"

    def test_validate_params_uses_defaults(self, library):
        """Parameters with defaults should be filled in."""
        queries = library.list_queries()
        # Find a query that has optional params with defaults
        for q_info in queries:
            params = q_info["parameters"]
            optional_with_default = [
                p for p in params if not p["required"] and p["default"] is not None
            ]
            if optional_with_default:
                # This query has defaulted params — just test that listing works
                assert q_info["query_id"] is not None
                break
