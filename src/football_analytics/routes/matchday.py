"""Matchday operations endpoints — fixtures, calendar, pre/post match, sync."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/matchday", tags=["matchday"])
logger = logging.getLogger(__name__)


# ─── Request Models ─────────────────────────────────────────────────────────


class FixtureCreateRequest(BaseModel):
    competition_id: int
    season_id: int
    match_date: str = Field(..., description="ISO date YYYY-MM-DD")
    kick_off: str | None = None
    home_team_id: int
    away_team_id: int
    venue_type: str = "home"
    stage: str = ""
    matchday: int = 0


class FixtureBatchCreateRequest(BaseModel):
    fixtures: list[FixtureCreateRequest]


class PostMatchRequest(BaseModel):
    match_id: int
    our_team_id: int | None = None


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/fixtures")
def get_matchday_fixtures(
    competition_id: int | None = Query(None),
    status: str | None = Query(None),
    days_ahead: int = Query(14),
    team_id: int | None = Query(None),
) -> dict[str, Any]:
    """Get fixtures with optional filters."""
    from datetime import date, timedelta

    from football_analytics.matchday.fixtures import FixtureManager, FixtureStatus

    try:
        manager = FixtureManager()
        status_enum = FixtureStatus(status) if status else None
        fixtures = manager.get_fixtures(
            competition_id=competition_id,
            status=status_enum,
            from_date=date.today(),
            to_date=date.today() + timedelta(days=days_ahead),
            team_id=team_id,
        )
        return {"count": len(fixtures), "fixtures": [manager._fixture_to_dict(f) for f in fixtures]}
    except Exception:
        logger.exception("Failed to get fixtures")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/calendar")
def get_matchday_calendar(
    days_ahead: int = Query(14),
    days_behind: int = Query(7),
) -> dict[str, Any]:
    """Get calendar summary for the matchday view."""
    from football_analytics.matchday.fixtures import FixtureManager

    try:
        manager = FixtureManager()
        return manager.get_calendar_summary(days_ahead=days_ahead, days_behind=days_behind)
    except Exception:
        logger.exception("Failed to get calendar")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/fixtures")
def create_fixture(request: FixtureCreateRequest) -> dict[str, Any]:
    """Create a new fixture."""
    from datetime import date as date_type

    from football_analytics.matchday.fixtures import Fixture, FixtureManager

    try:
        manager = FixtureManager()
        fixture = Fixture(
            competition_id=request.competition_id,
            season_id=request.season_id,
            match_date=date_type.fromisoformat(request.match_date),
            kick_off=request.kick_off,
            home_team_id=request.home_team_id,
            away_team_id=request.away_team_id,
            venue_type=request.venue_type,
            stage=request.stage,
            matchday=request.matchday,
        )
        fixture_id = manager.create_fixture(fixture)
        return {"fixture_id": fixture_id, "status": "created"}
    except Exception:
        logger.exception("Failed to create fixture")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/fixtures/batch")
def create_fixtures_batch(request: FixtureBatchCreateRequest) -> dict[str, Any]:
    """Create multiple fixtures in a single request."""
    from datetime import date as date_type

    from football_analytics.matchday.fixtures import Fixture, FixtureManager

    try:
        manager = FixtureManager()
        fixtures = [
            Fixture(
                competition_id=f.competition_id,
                season_id=f.season_id,
                match_date=date_type.fromisoformat(f.match_date),
                kick_off=f.kick_off,
                home_team_id=f.home_team_id,
                away_team_id=f.away_team_id,
                venue_type=f.venue_type,
                stage=f.stage,
                matchday=f.matchday,
            )
            for f in request.fixtures
        ]
        ids = manager.create_fixtures_batch(fixtures)
        return {"fixture_ids": ids, "count": len(ids)}
    except Exception:
        logger.exception("Failed to create fixtures batch")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/fixtures/{fixture_id}/status")
def update_fixture_status(
    fixture_id: int = Path(..., gt=0),
    status: str = Query(..., description="New status value"),
    match_id: int | None = Query(None),
) -> dict[str, Any]:
    """Update fixture lifecycle status."""
    from football_analytics.matchday.fixtures import FixtureManager, FixtureStatus

    try:
        status_enum = FixtureStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {[s.value for s in FixtureStatus]}",
        )

    try:
        manager = FixtureManager()
        manager.update_status(fixture_id, status_enum, match_id=match_id)
        return {"fixture_id": fixture_id, "status": status_enum.value}
    except Exception:
        logger.exception("Failed to update fixture status")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/fixtures/{fixture_id}/pre-match")
def get_pre_match_pack(
    fixture_id: int = Path(..., gt=0),
    our_team_id: int | None = Query(None),
) -> dict[str, Any]:
    """Generate or retrieve pre-match intelligence pack."""
    from dataclasses import asdict

    from football_analytics.matchday.pre_match import generate_pre_match_pack

    try:
        pack = generate_pre_match_pack(fixture_id=fixture_id, our_team_id=our_team_id)
        result = asdict(pack)
        result["generated_at"] = pack.generated_at.isoformat()
        if pack.match_date:
            result["match_date"] = pack.match_date.isoformat()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        logger.exception("Pre-match pack generation failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/fixtures/{fixture_id}/post-match")
def generate_post_match(request: PostMatchRequest, fixture_id: int = Path(..., gt=0)) -> dict[str, Any]:
    """Generate post-match review for a completed fixture."""
    from dataclasses import asdict

    from football_analytics.matchday.post_match import generate_post_match_review

    try:
        review = generate_post_match_review(
            match_id=request.match_id,
            our_team_id=request.our_team_id,
            fixture_id=fixture_id,
        )
        result = asdict(review)
        result["generated_at"] = review.generated_at.isoformat()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        logger.exception("Post-match review generation failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/needing-preview")
def get_fixtures_needing_preview() -> dict[str, Any]:
    """Get fixtures that need pre-match packs."""
    from football_analytics.matchday.fixtures import FixtureManager

    try:
        manager = FixtureManager()
        fixtures = manager.get_needing_preview()
        return {"count": len(fixtures), "fixtures": [manager._fixture_to_dict(f) for f in fixtures]}
    except Exception:
        logger.exception("Failed to get fixtures needing preview")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/needing-review")
def get_fixtures_needing_review() -> dict[str, Any]:
    """Get completed fixtures that haven't been reviewed."""
    from football_analytics.matchday.fixtures import FixtureManager

    try:
        manager = FixtureManager()
        fixtures = manager.get_needing_review()
        return {"count": len(fixtures), "fixtures": [manager._fixture_to_dict(f) for f in fixtures]}
    except Exception:
        logger.exception("Failed to get fixtures needing review")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── External Fixture Sync ──────────────────────────────────────────────────


@router.get("/competitions")
def get_supported_competitions() -> dict[str, Any]:
    """Get list of competitions available for fixture sync."""
    from football_analytics.matchday.fixture_sync import get_supported_competitions

    return {"competitions": get_supported_competitions()}


@router.get("/sync/{competition_code}")
def sync_competition_fixtures(competition_code: str) -> dict[str, Any]:
    """Fetch upcoming fixtures from football-data.org and sync to local DB."""
    from football_analytics.matchday.fixture_sync import Competition, sync_fixtures_to_db

    code = competition_code.upper()
    try:
        competition = Competition(code)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported competition code '{code}'. Must be one of: PL, CL, WC",
        )

    try:
        result = sync_fixtures_to_db(competition)
        return {"competition": competition.display_name, "code": code, **result}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("Fixture sync failed for %s", code)
        raise HTTPException(status_code=502, detail="External API error")


@router.get("/external/{competition_code}")
def get_external_fixtures(competition_code: str) -> dict[str, Any]:
    """Fetch upcoming fixtures from football-data.org without saving."""
    from football_analytics.matchday.fixture_sync import Competition, fetch_competition_fixtures

    code = competition_code.upper()
    try:
        competition = Competition(code)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported competition code '{code}'. Must be one of: PL, CL, WC",
        )

    try:
        fixtures = fetch_competition_fixtures(competition)
        return {
            "competition": competition.display_name,
            "code": code,
            "count": len(fixtures),
            "fixtures": [
                {
                    "external_id": f.external_id,
                    "match_date": f.match_date.isoformat() if f.match_date else None,
                    "kick_off": f.kick_off,
                    "home_team": {"id": f.home_team_id, "name": f.home_team_name},
                    "away_team": {"id": f.away_team_id, "name": f.away_team_name},
                    "matchday": f.matchday,
                    "stage": f.stage,
                    "status": f.status,
                    "competition_name": f.competition_name,
                }
                for f in fixtures
            ],
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("External fixture fetch failed for %s", code)
        raise HTTPException(status_code=502, detail="External API error")
