"""API route modules — split from monolithic api.py for maintainability."""

from football_analytics.routes.analysis import router as analysis_router
from football_analytics.routes.cache import router as cache_router
from football_analytics.routes.dashboard import router as dashboard_router
from football_analytics.routes.executive import router as executive_router
from football_analytics.routes.health import router as health_router
from football_analytics.routes.matchday import router as matchday_router
from football_analytics.routes.prediction import router as prediction_router

ALL_ROUTERS = [
    health_router,
    analysis_router,
    dashboard_router,
    prediction_router,
    matchday_router,
    executive_router,
    cache_router,
]

__all__ = ["ALL_ROUTERS"]
