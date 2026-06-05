"""FastAPI REST API layer for football analytics.

Exposes analysis functions as HTTP endpoints for:
- External integrations (Tableau, Power BI, mobile apps)
- Custom frontends (React SPA)
- Automated reporting pipelines
- Match prediction and simulation

Route modules are in football_analytics.routes.*
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

import football_analytics as _fa
from football_analytics.routes import ALL_ROUTERS
from football_analytics.routes.matchday import (  # noqa: F401
    FixtureBatchCreateRequest,
    FixtureCreateRequest,
    PostMatchRequest,
)

logger = logging.getLogger(__name__)

# ─── Rate Limiter Setup ─────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — runs migrations on startup."""
    import subprocess

    if os.getenv("DATABASE_URL") or os.getenv("POSTGRES_PASSWORD"):
        try:
            subprocess.run(
                ["alembic", "upgrade", "head"],
                timeout=30,
                capture_output=True,
                check=False,
            )
            logger.info("Alembic migrations applied successfully")
        except Exception as exc:
            logger.warning("Alembic migration skipped: %s", exc)
    yield


app = FastAPI(
    title="Football Analytics API",
    description="REST API for StatsBomb-based football data analysis",
    version=_fa.__version__,
    docs_url="/docs" if os.getenv("API_DOCS_ENABLED", "true").lower() == "true" else None,
    redoc_url="/redoc" if os.getenv("API_DOCS_ENABLED", "true").lower() == "true" else None,
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ─── Middleware ─────────────────────────────────────────────────────────────


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to each request for tracing."""

    async def dispatch(self, request: Request, call_next):
        import uuid

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "[%s] %s %s → %d (%.1fms)",
            request_id[:8],
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        return response


app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


# ─── Global Exception Handler ───────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions — never leak stack traces to clients."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ─── CORS ───────────────────────────────────────────────────────────────────

_allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
_validated_origins = [o.strip() for o in _allowed_origins if o.strip().startswith(("http://", "https://"))]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_validated_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "Authorization"],
)


# ─── Register Route Modules ────────────────────────────────────────────────

for router in ALL_ROUTERS:
    app.include_router(router)


# ─── Entry Point ────────────────────────────────────────────────────────────


def main() -> None:
    """Run the API server."""
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
