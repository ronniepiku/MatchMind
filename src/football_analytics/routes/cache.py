"""Cache and system endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/cache/stats")
def get_cache_stats():
    """Get Parquet cache statistics."""
    from football_analytics.cache import cache_stats

    return cache_stats()


class CacheInvalidateRequest(BaseModel):
    name: str | None = None


@router.post("/cache/invalidate")
def invalidate_cache_endpoint(request: CacheInvalidateRequest):
    """Invalidate cache entries (all or by name prefix)."""
    from football_analytics.cache import invalidate_cache

    count = invalidate_cache(request.name)
    return {"invalidated": count}


@router.get("/system/validation/{match_id}")
def validate_match(match_id: int):
    """Run data validation on a specific match."""
    from football_analytics.validation import DataValidator

    validator = DataValidator(log_to_db=False)
    report = validator.validate_match_events(match_id)
    return report.summary
