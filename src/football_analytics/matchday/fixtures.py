"""Multi-competition fixture management and lifecycle tracking.

Manages fixtures across multiple competitions simultaneously (e.g., Premier League
+ Champions League + World Cup). Tracks each fixture through its operational
lifecycle: scheduled → preview_generated → in_progress → completed → reviewed.

Designed for daily use by an analyst team supporting multiple squads.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)


class FixtureStatus(Enum):
    """Lifecycle status of a fixture."""

    SCHEDULED = "scheduled"
    PREVIEW_GENERATED = "preview_generated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEWED = "reviewed"


class FixturePriority(Enum):
    """Operational priority for fixture processing."""

    CRITICAL = 1  # First-team competitive (league, CL knockout)
    HIGH = 2  # First-team group stage, domestic cup
    MEDIUM = 3  # Women's team, academy competitive
    LOW = 4  # Friendlies, development matches


@dataclass
class Fixture:
    """A scheduled match within the operational calendar."""

    fixture_id: int | None = None
    competition_id: int = 0
    competition_name: str = ""
    season_id: int = 0
    match_date: date | None = None
    kick_off: str | None = None
    home_team_id: int = 0
    home_team_name: str = ""
    away_team_id: int = 0
    away_team_name: str = ""
    venue_type: str = "home"  # home, away, neutral
    stage: str = ""  # "Matchweek 12", "Group A", "Quarter-Final"
    matchday: int = 0
    status: FixtureStatus = FixtureStatus.SCHEDULED
    priority: FixturePriority = FixturePriority.HIGH
    match_id: int | None = None  # Links to matches table after completion
    notes: str = ""

    @property
    def is_upcoming(self) -> bool:
        """Whether fixture is in the future."""
        if self.match_date is None:
            return True
        return self.match_date >= date.today()

    @property
    def days_until(self) -> int | None:
        """Days until match (negative if past)."""
        if self.match_date is None:
            return None
        return (self.match_date - date.today()).days

    @property
    def needs_preview(self) -> bool:
        """Whether a pre-match pack should be generated."""
        return (
            self.status == FixtureStatus.SCHEDULED
            and self.is_upcoming
            and self.days_until is not None
            and self.days_until <= 3
        )

    @property
    def display_name(self) -> str:
        """Human-readable fixture label."""
        return f"{self.home_team_name} vs {self.away_team_name}"


class FixtureManager:
    """Manages fixtures across multiple competitions.

    Provides CRUD operations, status lifecycle management, and
    filtered queries for the matchday calendar.

    Usage:
        manager = FixtureManager(engine)
        upcoming = manager.get_upcoming(days_ahead=7)
        manager.update_status(fixture_id=1, status=FixtureStatus.PREVIEW_GENERATED)
    """

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def get_fixtures(
        self,
        competition_id: int | None = None,
        status: FixtureStatus | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        team_id: int | None = None,
    ) -> list[Fixture]:
        """Query fixtures with optional filters.

        Args:
            competition_id: Filter to specific competition.
            status: Filter by lifecycle status.
            from_date: Fixtures on or after this date.
            to_date: Fixtures on or before this date.
            team_id: Fixtures involving this team (home or away).

        Returns:
            List of Fixture objects sorted by match_date.
        """
        conditions = []
        params: dict[str, Any] = {}

        if competition_id is not None:
            conditions.append("f.competition_id = :comp_id")
            params["comp_id"] = competition_id
        if status is not None:
            conditions.append("f.status = :status")
            params["status"] = status.value
        if from_date is not None:
            conditions.append("f.match_date >= :from_date")
            params["from_date"] = from_date
        if to_date is not None:
            conditions.append("f.match_date <= :to_date")
            params["to_date"] = to_date
        if team_id is not None:
            conditions.append("(f.home_team_id = :team_id OR f.away_team_id = :team_id)")
            params["team_id"] = team_id

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = text(f"""
            SELECT f.fixture_id, f.competition_id, c.competition_name,
                   f.season_id, f.match_date, f.kick_off,
                   f.home_team_id, ht.team_name AS home_team_name,
                   f.away_team_id, at.team_name AS away_team_name,
                   f.venue_type, f.stage, f.matchday, f.status, f.match_id
            FROM fixtures f
            JOIN teams ht ON f.home_team_id = ht.team_id
            JOIN teams at ON f.away_team_id = at.team_id
            LEFT JOIN competitions c ON f.competition_id = c.competition_id
                AND f.season_id = c.season_id
            {where}
            ORDER BY f.match_date ASC, f.fixture_id ASC
        """)

        with self._engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)

        return [self._row_to_fixture(row) for _, row in df.iterrows()]

    def get_upcoming(self, days_ahead: int = 7) -> list[Fixture]:
        """Get fixtures in the next N days."""
        return self.get_fixtures(
            from_date=date.today(),
            to_date=date.today() + timedelta(days=days_ahead),
        )

    def get_needing_preview(self) -> list[Fixture]:
        """Get fixtures that need pre-match packs generated (within 3 days, no pack yet)."""
        fixtures = self.get_fixtures(
            status=FixtureStatus.SCHEDULED,
            from_date=date.today(),
            to_date=date.today() + timedelta(days=3),
        )
        return [f for f in fixtures if f.needs_preview]

    def get_needing_review(self) -> list[Fixture]:
        """Get completed fixtures that haven't been reviewed yet."""
        return self.get_fixtures(status=FixtureStatus.COMPLETED)

    def create_fixture(self, fixture: Fixture) -> int:
        """Create a new fixture in the database.

        Returns:
            The generated fixture_id.
        """
        query = text("""
            INSERT INTO fixtures (competition_id, season_id, match_date, kick_off,
                                  home_team_id, away_team_id, venue_type, stage,
                                  matchday, status)
            VALUES (:comp_id, :season_id, :match_date, :kick_off,
                    :home_team_id, :away_team_id, :venue_type, :stage,
                    :matchday, :status)
            RETURNING fixture_id
        """)

        with self._engine.begin() as conn:
            result = conn.execute(
                query,
                {
                    "comp_id": fixture.competition_id,
                    "season_id": fixture.season_id,
                    "match_date": fixture.match_date,
                    "kick_off": fixture.kick_off,
                    "home_team_id": fixture.home_team_id,
                    "away_team_id": fixture.away_team_id,
                    "venue_type": fixture.venue_type,
                    "stage": fixture.stage,
                    "matchday": fixture.matchday,
                    "status": fixture.status.value,
                },
            )
            fixture_id = result.scalar_one()

        logger.info(f"Created fixture {fixture_id}: {fixture.display_name}")
        return fixture_id

    def create_fixtures_batch(self, fixtures: list[Fixture]) -> list[int]:
        """Create multiple fixtures in a single transaction."""
        ids = []
        for fixture in fixtures:
            fid = self.create_fixture(fixture)
            ids.append(fid)
        return ids

    def update_status(
        self,
        fixture_id: int,
        status: FixtureStatus,
        match_id: int | None = None,
    ) -> None:
        """Update fixture lifecycle status.

        Args:
            fixture_id: Fixture to update.
            status: New status.
            match_id: Link to matches table (when completed).
        """
        params: dict[str, Any] = {
            "fixture_id": fixture_id,
            "status": status.value,
        }

        set_clause = "status = :status, updated_at = NOW()"
        if match_id is not None:
            set_clause += ", match_id = :match_id"
            params["match_id"] = match_id

        query = text(f"UPDATE fixtures SET {set_clause} WHERE fixture_id = :fixture_id")

        with self._engine.begin() as conn:
            conn.execute(query, params)

        logger.info(f"Fixture {fixture_id} status → {status.value}")

    def link_to_match(self, fixture_id: int, match_id: int) -> None:
        """Link a fixture to its actual match result after the game is played."""
        self.update_status(fixture_id, FixtureStatus.COMPLETED, match_id=match_id)

    def get_calendar_summary(self, days_ahead: int = 14, days_behind: int = 7) -> dict[str, Any]:
        """Get a summary view of the matchday calendar.

        Returns a dict suitable for dashboard display with:
        - upcoming fixtures (next N days)
        - recent results (last N days)
        - status counts
        """
        upcoming = self.get_fixtures(
            from_date=date.today(),
            to_date=date.today() + timedelta(days=days_ahead),
        )
        recent = self.get_fixtures(
            from_date=date.today() - timedelta(days=days_behind),
            to_date=date.today() - timedelta(days=1),
        )
        needing_preview = [f for f in upcoming if f.needs_preview]
        needing_review = [f for f in recent if f.status == FixtureStatus.COMPLETED]

        return {
            "upcoming_count": len(upcoming),
            "upcoming_fixtures": [self._fixture_to_dict(f) for f in upcoming[:10]],
            "recent_results": [self._fixture_to_dict(f) for f in recent[:10]],
            "needing_preview": len(needing_preview),
            "needing_review": len(needing_review),
            "status_counts": {
                "scheduled": sum(1 for f in upcoming if f.status == FixtureStatus.SCHEDULED),
                "preview_generated": sum(1 for f in upcoming if f.status == FixtureStatus.PREVIEW_GENERATED),
                "completed": len([f for f in recent if f.status == FixtureStatus.COMPLETED]),
                "reviewed": len([f for f in recent if f.status == FixtureStatus.REVIEWED]),
            },
        }

    def _row_to_fixture(self, row: pd.Series) -> Fixture:
        """Convert a database row to Fixture dataclass."""
        match_date_val = row.get("match_date")
        if isinstance(match_date_val, str):
            match_date_val = date.fromisoformat(match_date_val)
        elif isinstance(match_date_val, datetime):
            match_date_val = match_date_val.date()

        return Fixture(
            fixture_id=int(row["fixture_id"]),
            competition_id=int(row["competition_id"]),
            competition_name=str(row.get("competition_name") or ""),
            season_id=int(row["season_id"]),
            match_date=match_date_val,
            kick_off=str(row.get("kick_off") or ""),
            home_team_id=int(row["home_team_id"]),
            home_team_name=str(row["home_team_name"]),
            away_team_id=int(row["away_team_id"]),
            away_team_name=str(row["away_team_name"]),
            venue_type=str(row.get("venue_type") or "home"),
            stage=str(row.get("stage") or ""),
            matchday=int(row.get("matchday") or 0),
            status=FixtureStatus(row.get("status", "scheduled")),
            match_id=int(row["match_id"]) if row.get("match_id") else None,
        )

    def _fixture_to_dict(self, fixture: Fixture) -> dict[str, Any]:
        """Convert Fixture to JSON-serialisable dict."""
        return {
            "fixture_id": fixture.fixture_id,
            "competition_name": fixture.competition_name,
            "match_date": (fixture.match_date.isoformat() if fixture.match_date else None),
            "kick_off": fixture.kick_off,
            "home_team": {"id": fixture.home_team_id, "name": fixture.home_team_name},
            "away_team": {"id": fixture.away_team_id, "name": fixture.away_team_name},
            "venue_type": fixture.venue_type,
            "stage": fixture.stage,
            "status": fixture.status.value,
            "days_until": fixture.days_until,
            "priority": fixture.priority.value,
        }
