"""Health and readiness endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import football_analytics as _fa

router = APIRouter(prefix="/api/v1", tags=["health"])


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = _fa.__version__


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()


@router.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness check — verifies database connectivity.

    Use this for Kubernetes/Railway readiness probes. Unlike /health,
    this actually checks that the database is reachable.
    """
    from football_analytics.db import check_connectivity

    db_ok = check_connectivity()
    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unreachable"},
        )
    return {"status": "ready", "database": "connected"}
