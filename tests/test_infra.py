"""Tests for infrastructure modules (ingestion orchestrator + model versioning)."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from football_analytics.ingest_orchestrator import (
    CompetitionRegistry,
    IngestionOrchestrator,
)
from football_analytics.prediction.model_versioning import (
    MODEL_VERSION,
    AccuracyReport,
    ModelVersion,
    PredictionRecord,
    PredictionVersionManager,
)

# ─── CompetitionRegistry Tests ────────────────────────────────────────────────


class TestCompetitionRegistry:
    """Tests for the competition registry dataclass."""

    def test_defaults(self):
        reg = CompetitionRegistry(
            competition_id=43,
            season_id=106,
            competition_name="World Cup 2026",
        )
        assert reg.is_active is True
        assert reg.last_sync is None
        assert reg.matches_synced == 0
        assert reg.priority == 1

    def test_all_fields(self):
        reg = CompetitionRegistry(
            competition_id=2,
            season_id=90,
            competition_name="Premier League",
            country="England",
            is_active=True,
            last_sync=datetime(2025, 1, 1),
            matches_synced=200,
            total_matches=380,
            priority=1,
        )
        assert reg.country == "England"
        assert reg.matches_synced == 200


# ─── IngestionOrchestrator Tests ──────────────────────────────────────────────


class TestIngestionOrchestrator:
    """Tests for the ingestion orchestrator (mocked DB)."""

    @pytest.fixture
    def mock_engine(self):
        return MagicMock()

    @pytest.fixture
    def orchestrator(self, mock_engine):
        return IngestionOrchestrator(engine=mock_engine)

    def test_instantiation(self, orchestrator):
        assert orchestrator is not None

    def test_register_competition(self, orchestrator, mock_engine):
        """Register should execute SQL to insert/upsert into registry."""
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        orchestrator.register_competition(
            competition_id=2,
            season_id=90,
            name="Premier League",
            country="England",
        )
        # Should have called execute at least once
        mock_conn.execute.assert_called()

    def test_get_sync_status(self, orchestrator, mock_engine):
        """get_sync_status queries the registry table."""
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("pandas.read_sql") as mock_read:
            mock_read.return_value = pd.DataFrame(
                {
                    "competition_id": [2],
                    "season_id": [90],
                    "competition_name": ["Premier League"],
                    "matches_synced": [200],
                    "total_matches": [380],
                    "is_active": [True],
                }
            )
            status = orchestrator.get_sync_status()
            assert isinstance(status, (list, pd.DataFrame))


# ─── ModelVersion Tests ───────────────────────────────────────────────────────


class TestModelVersion:
    """Tests for model version metadata."""

    def test_params_hash_deterministic(self):
        v1 = ModelVersion(
            version="1.0.0",
            description="Initial",
            algorithm="dixon_coles",
            parameters={"decay": 0.0065, "home_advantage": True},
        )
        v2 = ModelVersion(
            version="1.0.0",
            description="Initial",
            algorithm="dixon_coles",
            parameters={"home_advantage": True, "decay": 0.0065},
        )
        # Same params in different order → same hash
        assert v1.params_hash == v2.params_hash

    def test_different_params_different_hash(self):
        v1 = ModelVersion(
            version="1.0.0",
            description="V1",
            algorithm="dixon_coles",
            parameters={"decay": 0.0065},
        )
        v2 = ModelVersion(
            version="1.1.0",
            description="V2",
            algorithm="dixon_coles",
            parameters={"decay": 0.008},
        )
        assert v1.params_hash != v2.params_hash


class TestMODEL_VERSION:
    """Tests for the module-level version constant."""

    def test_semantic_version_format(self):
        parts = MODEL_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


# ─── PredictionVersionManager Tests ──────────────────────────────────────────


class TestPredictionVersionManager:
    """Tests for prediction version management (mocked DB)."""

    @pytest.fixture
    def mock_engine(self):
        return MagicMock()

    @pytest.fixture
    def manager(self, mock_engine):
        return PredictionVersionManager(engine=mock_engine)

    def test_instantiation(self, manager):
        assert manager is not None

    def test_store_prediction(self, manager, mock_engine):
        """store_prediction should persist a prediction record."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 1
        mock_engine.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        result = manager.store_prediction(
            match_id=1001,
            home_win_prob=0.45,
            draw_prob=0.28,
            away_win_prob=0.27,
            confidence="high",
        )
        mock_conn.execute.assert_called()

    def test_accuracy_report_with_no_data(self, manager, mock_engine):
        """accuracy_report with empty data should handle gracefully."""
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("pandas.read_sql") as mock_read:
            mock_read.return_value = pd.DataFrame()
            report = manager.accuracy_report()
            assert report is not None
