"""External fixture synchronisation from football-data.org API.

Fetches upcoming fixtures for supported competitions and upserts them
into the local fixtures table so the Matchday Calendar is always current.

Supported competitions (football-data.org codes):
    PL  - Premier League
    CL  - UEFA Champions League
    WC  - FIFA World Cup

Requires FOOTBALL_DATA_API_KEY environment variable.
Free tier: 10 requests/minute.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

import httpx

from football_analytics.db import get_engine
from football_analytics.matchday.fixtures import Fixture, FixtureManager, FixtureStatus

logger = logging.getLogger(__name__)

# football-data.org base URL
_BASE_URL = "https://api.football-data.org/v4"

# Request timeout
_TIMEOUT = 15.0


class Competition(Enum):
    """Supported competitions with football-data.org codes."""

    PREMIER_LEAGUE = "PL"
    CHAMPIONS_LEAGUE = "CL"
    WORLD_CUP = "WC"

    @property
    def display_name(self) -> str:
        names = {
            "PL": "Premier League",
            "CL": "UEFA Champions League",
            "WC": "FIFA World Cup",
        }
        return names[self.value]

    @property
    def internal_id(self) -> int:
        """Map to internal competition_id for the fixtures table."""
        ids = {
            "PL": 2021,
            "CL": 2001,
            "WC": 2000,
        }
        return ids[self.value]


@dataclass
class ExternalFixture:
    """A fixture fetched from football-data.org."""

    external_id: int
    competition_code: str
    competition_name: str
    season_year: int
    match_date: date | None
    kick_off: str | None
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
    matchday: int
    stage: str
    status: str  # SCHEDULED, TIMED, IN_PLAY, FINISHED, etc.

    @property
    def is_upcoming(self) -> bool:
        if self.match_date is None:
            return True
        return self.match_date >= date.today()


def _get_api_key() -> str:
    """Get football-data.org API key from environment."""
    key = os.getenv("FOOTBALL_DATA_API_KEY", "")
    if not key:
        raise RuntimeError(
            "FOOTBALL_DATA_API_KEY environment variable is required. "
            "Get a free key at https://www.football-data.org/client/register"
        )
    return key


def _make_headers() -> dict[str, str]:
    return {"X-Auth-Token": _get_api_key()}


def fetch_competition_fixtures(
    competition: Competition,
    status: str = "SCHEDULED",
    limit: int = 50,
) -> list[ExternalFixture]:
    """Fetch fixtures from football-data.org for a competition.

    Args:
        competition: Which competition to fetch.
        status: Match status filter (SCHEDULED, TIMED, LIVE, IN_PLAY, FINISHED).
        limit: Maximum number of fixtures to return.

    Returns:
        List of ExternalFixture objects.
    """
    url = f"{_BASE_URL}/competitions/{competition.value}/matches"
    params: dict[str, Any] = {"status": status, "limit": limit}

    logger.info(f"Fetching {competition.display_name} fixtures (status={status})")

    response = httpx.get(url, headers=_make_headers(), params=params, timeout=_TIMEOUT)
    response.raise_for_status()

    data = response.json()
    matches = data.get("matches", [])
    season_year = data.get("filters", {}).get("season", datetime.now().year)

    fixtures: list[ExternalFixture] = []
    for match in matches:
        utc_date = match.get("utcDate")
        match_date = None
        kick_off = None
        if utc_date:
            dt = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
            match_date = dt.date()
            kick_off = dt.strftime("%H:%M")

        fixtures.append(
            ExternalFixture(
                external_id=match["id"],
                competition_code=competition.value,
                competition_name=competition.display_name,
                season_year=season_year if isinstance(season_year, int) else datetime.now().year,
                match_date=match_date,
                kick_off=kick_off,
                home_team_id=match["homeTeam"]["id"],
                home_team_name=match["homeTeam"].get("shortName") or match["homeTeam"]["name"],
                away_team_id=match["awayTeam"]["id"],
                away_team_name=match["awayTeam"].get("shortName") or match["awayTeam"]["name"],
                matchday=match.get("matchday") or 0,
                stage=match.get("stage", "").replace("_", " ").title(),
                status=match.get("status", "SCHEDULED"),
            )
        )

    logger.info(f"Fetched {len(fixtures)} fixtures for {competition.display_name}")
    return fixtures


def fetch_all_fixtures(
    competitions: list[Competition] | None = None,
) -> dict[str, list[ExternalFixture]]:
    """Fetch fixtures for multiple competitions.

    Args:
        competitions: List of competitions. Defaults to all supported.

    Returns:
        Dict mapping competition code to list of fixtures.
    """
    if competitions is None:
        competitions = list(Competition)

    results: dict[str, list[ExternalFixture]] = {}
    for comp in competitions:
        try:
            results[comp.value] = fetch_competition_fixtures(comp)
        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch {comp.display_name}: {e.response.status_code}")
            results[comp.value] = []
        except Exception as e:
            logger.warning(f"Failed to fetch {comp.display_name}: {e}")
            results[comp.value] = []

    return results


def sync_fixtures_to_db(
    competition: Competition,
    fixtures: list[ExternalFixture] | None = None,
) -> dict[str, int]:
    """Sync external fixtures into the local database.

    Fetches from API if fixtures not provided, then upserts into the
    fixtures table. Uses external_id to detect duplicates.

    Args:
        competition: Which competition to sync.
        fixtures: Pre-fetched fixtures (fetches from API if None).

    Returns:
        Dict with counts: {"created": N, "skipped": N, "total": N}
    """
    if fixtures is None:
        fixtures = fetch_competition_fixtures(competition)

    engine = get_engine()
    manager = FixtureManager(engine)

    # Get existing fixture external IDs to avoid duplicates
    existing_external_ids = _get_existing_external_ids(competition)

    created = 0
    skipped = 0

    for ext in fixtures:
        if ext.external_id in existing_external_ids:
            skipped += 1
            continue

        # Map to internal fixture
        fixture = Fixture(
            competition_id=competition.internal_id,
            competition_name=competition.display_name,
            season_id=ext.season_year,
            match_date=ext.match_date,
            kick_off=ext.kick_off,
            home_team_id=ext.home_team_id,
            home_team_name=ext.home_team_name,
            away_team_id=ext.away_team_id,
            away_team_name=ext.away_team_name,
            venue_type="home",
            stage=ext.stage or f"Matchday {ext.matchday}",
            matchday=ext.matchday,
            status=FixtureStatus.SCHEDULED,
            notes=f"external_id:{ext.external_id}",
        )

        try:
            manager.create_fixture(fixture)
            created += 1
        except Exception as e:
            logger.warning(f"Failed to create fixture {ext.external_id}: {e}")
            skipped += 1

    logger.info(f"Sync {competition.display_name}: created={created}, skipped={skipped}")
    return {"created": created, "skipped": skipped, "total": len(fixtures)}


def _get_existing_external_ids(competition: Competition) -> set[int]:
    """Get external IDs already in the fixtures table for deduplication."""
    from sqlalchemy import text

    engine = get_engine()
    query = text("""
        SELECT notes FROM fixtures
        WHERE competition_id = :comp_id AND notes LIKE 'external_id:%'
    """)

    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {"comp_id": competition.internal_id}).fetchall()
        return {int(row[0].split("external_id:")[1]) for row in rows if row[0] and "external_id:" in row[0]}
    except Exception:
        # Table may not exist yet
        return set()


def get_supported_competitions() -> list[dict[str, str]]:
    """Return list of supported competitions for frontend display."""
    return [{"code": c.value, "name": c.display_name, "id": c.internal_id} for c in Competition]
