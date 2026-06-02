# Multi-stage Dockerfile for Football Analytics
# Stage 1: Base with uv and Python
# Stage 2: App with dependencies installed

# --- Base Stage ---
FROM python:3.11-slim AS base

# Install system dependencies for psycopg2 and matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# --- Dependencies Stage ---
FROM base AS deps

# Copy project metadata first (layer caching)
COPY pyproject.toml ./
COPY src/football_analytics/__init__.py src/football_analytics/__init__.py

# Install dependencies (cached unless pyproject.toml changes)
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

# --- App Stage ---
FROM deps AS app

# Copy application code
COPY src/ src/
COPY data/ data/
COPY notebooks/ notebooks/

# Run as non-root user
RUN useradd -r -s /bin/false appuser && chown -R appuser:appuser /app
USER appuser

# Expose API port
EXPOSE 8080

# Default: run the API server
CMD ["uv", "run", "fb-api"]
