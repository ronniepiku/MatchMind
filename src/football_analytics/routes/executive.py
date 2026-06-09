"""Executive intelligence and ad-hoc analysis endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["executive"])
logger = logging.getLogger(__name__)


# ─── Request Models ─────────────────────────────────────────────────────────


class PlayerAssessmentRequest(BaseModel):
    player_id: int
    season_id: int | None = None


class CompetitionOutlookRequest(BaseModel):
    team_id: int
    competition_id: int
    season_id: int


class PostMatchSummaryRequest(BaseModel):
    match_id: int
    our_team_id: int | None = None


class QueryExecutionRequest(BaseModel):
    query_id: str
    parameters: dict[str, Any]


# ─── Executive Endpoints ────────────────────────────────────────────────────


@router.get("/executive/weekly-briefing")
def get_weekly_briefing(
    team_id: int = Query(...),
    season_id: int | None = Query(None),
) -> dict[str, Any]:
    """Generate weekly executive briefing."""
    from dataclasses import asdict

    from football_analytics.reports.executive import ExecutiveReportGenerator

    try:
        gen = ExecutiveReportGenerator()
        briefing = gen.weekly_briefing(team_id=team_id, season_id=season_id)
        result = asdict(briefing)
        result["generated_at"] = briefing.generated_at.isoformat()
        result["week_difficulty"] = briefing.week_difficulty.value
        for m in result.get("squad_metrics", []):
            m["rag"] = m["rag"].value if hasattr(m.get("rag"), "value") else m["rag"]
            m["trend"] = m["trend"].value if hasattr(m.get("trend"), "value") else m["trend"]
        return result
    except Exception as exc:
        logger.exception("Weekly briefing generation failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/executive/player-assessment")
def get_player_assessment(request: PlayerAssessmentRequest) -> dict[str, Any]:
    """Generate executive player assessment."""
    from dataclasses import asdict

    from football_analytics.reports.executive import ExecutiveReportGenerator

    try:
        gen = ExecutiveReportGenerator()
        assessment = gen.player_assessment(player_id=request.player_id, season_id=request.season_id)
        result = asdict(assessment)
        result["trajectory"] = assessment.trajectory.value
        for k in result.get("kpis", []):
            k["rag"] = k["rag"].value if hasattr(k.get("rag"), "value") else k["rag"]
            k["trend"] = k["trend"].value if hasattr(k.get("trend"), "value") else k["trend"]
        return result
    except Exception:
        logger.exception("Player assessment generation failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/executive/competition-outlook")
def get_competition_outlook(request: CompetitionOutlookRequest) -> dict[str, Any]:
    """Generate competition campaign outlook."""
    from dataclasses import asdict

    from football_analytics.reports.executive import ExecutiveReportGenerator

    try:
        gen = ExecutiveReportGenerator()
        outlook = gen.competition_outlook(
            team_id=request.team_id,
            competition_id=request.competition_id,
            season_id=request.season_id,
        )
        result = asdict(outlook)
        result["form_rag"] = outlook.form_rag.value
        return result
    except Exception:
        logger.exception("Competition outlook generation failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/executive/post-match-summary")
def get_post_match_executive_summary(request: PostMatchSummaryRequest) -> dict[str, Any]:
    """Generate one-page post-match executive summary."""
    from dataclasses import asdict

    from football_analytics.reports.executive import ExecutiveReportGenerator

    try:
        gen = ExecutiveReportGenerator()
        summary = gen.post_match_summary(match_id=request.match_id, our_team_id=request.our_team_id)
        result = asdict(summary)
        result["result_rag"] = summary.result_rag.value
        for m in result.get("key_metrics", []):
            m["rag"] = m["rag"].value if hasattr(m.get("rag"), "value") else m["rag"]
            m["trend"] = m["trend"].value if hasattr(m.get("trend"), "value") else m["trend"]
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        logger.exception("Post-match summary generation failed")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Ad-Hoc Analysis Endpoints ─────────────────────────────────────────────


@router.get("/analysis/queries")
def list_analysis_queries(category: str | None = Query(None)) -> dict[str, Any]:
    """List available analytical queries."""
    from football_analytics.analysis.queries import AnalyticalQueryLibrary

    try:
        library = AnalyticalQueryLibrary()
        queries = library.list_queries(category=category)
        categories = library.get_categories()
        return {"categories": categories, "queries": queries, "count": len(queries)}
    except Exception:
        logger.exception("Failed to list analysis queries")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/analysis/query")
def execute_analysis_query(request: QueryExecutionRequest) -> dict[str, Any]:
    """Execute a parameterised analytical query."""
    from football_analytics.analysis.queries import AnalyticalQueryLibrary

    try:
        library = AnalyticalQueryLibrary()
        results = library.execute_to_dict(request.query_id, request.parameters)
        return {
            "query_id": request.query_id,
            "parameters": request.parameters,
            "row_count": len(results),
            "results": results,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Query execution failed: %s", request.query_id)
        raise HTTPException(status_code=500, detail="Internal server error")
