# Multi-stage Dockerfile for Football Analytics
# Optimised for Railway deployment with health checks

# --- Base Stage ---
FROM python:3.11-slim AS base

# Install system dependencies for psycopg2 and matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# --- Dependencies Stage ---
FROM base AS deps

# Copy project metadata first (layer caching)
COPY pyproject.toml README.md ./
COPY src/football_analytics/__init__.py src/football_analytics/__init__.py

# Install dependencies (cached unless pyproject.toml changes)
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# --- App Stage ---
FROM deps AS app

# Copy application code
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini alembic.ini
COPY data/ data/

# Run as non-root user
RUN useradd -r -s /bin/false appuser \
    && mkdir -p /home/appuser/.cache/uv \
    && chown -R appuser:appuser /app /home/appuser
USER appuser

# Health check for container orchestrators
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/api/v1/health || exit 1

# Expose API port (Render/Railway sets PORT env var)
EXPOSE ${PORT:-8080}

# Run migrations then start API server
CMD ["sh", "-c", "uv run --no-sync alembic upgrade head || echo 'WARNING: Migration failed'; uv run --no-sync uvicorn football_analytics.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
