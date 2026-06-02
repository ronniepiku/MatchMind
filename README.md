# MatchMind - A football analytics Platform

[![CI](https://github.com/YOUR_USERNAME/football-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/ronniepiku/MatchMind/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

Match Mind is a **Production-grade football data analysis pipeline**. From raw StatsBomb event data to actionable tactical insights, interactive dashboards, automated PDF reports, Monte Carlo match simulation, and coaching-ready presentations.

## Key Features

- **React analytics dashboard**: Custom-built UI deployed on GitHub Pages with D3 pitch visualisations, dark/light theme
- **High-performance data pipeline**: COPY-protocol bulk loading + async concurrent fetching (3-4x faster)
- **Core analyses**: Opponent profiling, player performance, xG/xA, passing networks, pressing heatmaps
- **Custom xG model**: Trainable logistic regression + gradient boosting upgrade with hyperparameter tuning
- **Player similarity engine**: Embedding-based player comparison for recruitment shortlisting
- **Possession chain analysis**: Sequence modelling of build-up patterns, transitions, and dangerous possessions
- **Set-piece analysis**: Corner/free-kick clustering, delivery zone classification, efficiency metrics
- **Match simulation**: Monte Carlo outcome prediction with scoreline probabilities and in-match updates
- **Player development tracking**: Longitudinal trajectory analysis, breakout identification, age curves
- **Spatial dominance**: Voronoi tessellation, passing lanes, defensive coverage gaps
- **Video timestamp alignment**: Event-to-broadcast sync, FFmpeg clip generation, SRT subtitles
- **Tracking data integration**: Pitch control, physical metrics, and event synchronisation
- **FastAPI REST layer**: Full API for external integrations and the React frontend
- **Automated PDF reports**: Match reports, opponent scouts, and player profiles via Jinja2 + WeasyPrint
- **Parquet cache layer**: Instant notebook/dashboard loads bypassing database for read-heavy workflows
- **Performance-optimised**: Indexed queries (70x speedup), COPY protocol (5-10x), async I/O (3-4x)
- **Production engineering**: Type hints, unit tests, CI/CD, Docker, modular package structure

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 20+ and npm
- PostgreSQL 14+ (or use Docker Compose)

### Setup

```bash
# Clone the repo
git clone https://github.com/ronniepiku/MatchMind.git
cd MatchMind

# Install Python dependencies
uv sync

# Install frontend dependencies
npm run install:frontend

# Start PostgreSQL (via Docker)
docker compose up -d db

# Configure environment
cp .env.example .env  # Edit credentials if needed

# Ingest sample data (3 matches for quick demo)
uv run fb-ingest --max-matches 3

# Or use async ingestion (3-4x faster for full datasets)
uv run fb-ingest-async --max-matches 3

# Run backend tests
uv run pytest

# Start the API server
uv run fb-api
# → http://localhost:8080/docs

# Start the frontend dashboard (in a separate terminal)
npm run dev
# → http://localhost:5173

# Generate a PDF report
uv run fb-report --type opponent --team-id 771 --season-id 106
```

### Without Docker (Local PostgreSQL)

```bash
# Create database
createdb football_analytics
psql football_analytics < src/football_analytics/db/schema.sql

# Set connection in .env
echo "POSTGRES_HOST=localhost" >> .env

# Ingest and run
uv sync
uv run fb-ingest --competition-id 43 --season-id 106
uv run fb-api
```

### Full Docker Environment

```bash
docker compose up --build
# API: http://localhost:8080/docs
# Postgres: localhost:5433
# Frontend: run `npm run dev` separately (or deploy to GitHub Pages)
```

## Project Structure

```
MatchMind/
├── frontend/                    # React + TypeScript dashboard (Vite)
│   ├── src/
│   │   ├── api/                 # HTTP client, types, endpoint functions
│   │   ├── components/
│   │   │   ├── charts/          # Recharts + D3 visualisations
│   │   │   ├── layout/          # Sidebar, header, page wrapper
│   │   │   ├── pitch/           # SVG football pitch (StatsBomb coords)
│   │   │   └── shared/          # DataTable, cards, loading states
│   │   ├── hooks/               # useTheme, custom hooks
│   │   ├── pages/               # Route-level page components
│   │   └── styles/              # Tailwind CSS + custom properties theme
│   ├── vite.config.ts           # Build config (GitHub Pages base path)
│   └── package.json             # Frontend dependencies
├── src/football_analytics/
│   ├── __init__.py              # Package root
│   ├── config.py                # Environment & settings
│   ├── ingest.py                # Sync ingestion (COPY protocol)
│   ├── async_ingest.py          # Async concurrent ingestion (httpx)
│   ├── cache.py                 # Parquet cache layer
│   ├── api.py                   # FastAPI REST endpoints
│   ├── db/
│   │   ├── __init__.py          # Engine & session management
│   │   ├── schema.sql           # DDL + indexes + materialised views
│   │   ├── partitioning.sql     # Table partitioning by season_id
│   │   └── queries.sql          # Optimised analytical queries
│   ├── analysis/
│   │   ├── opponent_profile.py  # Opponent scouting reports
│   │   ├── player_performance.py # Player metrics & radar charts
│   │   ├── visualisations.py    # Static + interactive plots
│   │   ├── xg_model.py          # Custom xG model (logistic regression)
│   │   ├── xg_model_advanced.py # Gradient boosting xG (HistGradient)
│   │   ├── similarity.py        # Player similarity engine
│   │   ├── tracking.py          # Tracking data integration
│   │   ├── possession_chains.py # Possession sequence analysis
│   │   ├── set_pieces.py        # Set-piece analysis & clustering
│   │   ├── simulation.py        # Monte Carlo match simulation
│   │   ├── development.py       # Player development tracking
│   │   ├── spatial.py           # Voronoi tessellation & space control
│   │   └── video_alignment.py   # Video timestamp sync & clip generation
│   └── reports/
│       ├── pdf_report.py        # Automated PDF generation
│       └── templates/           # Jinja2 HTML report templates
├── tests/                       # Unit tests (pytest)
├── notebooks/                   # Reproducible Jupyter analyses
├── docs/                        # Technical docs
├── data/                        # Raw + processed + cache (gitignored)
├── .github/workflows/
│   ├── ci.yml                   # Backend CI (lint, type-check, test)
│   └── deploy-frontend.yml      # GitHub Pages frontend deployment
├── Dockerfile                   # Container build
├── docker-compose.yml           # Full stack orchestration
├── pyproject.toml               # Python dependencies (uv/hatch)
├── package.json                 # Root convenience scripts → frontend/
└── README.md                    # This file
```

## Analyses & Modules

| Module | Capability | Use Case |
|--------|-----------|----------|
| `opponent_profile.py` | Attack patterns, defensive shape, key threats | Pre-match preparation |
| `player_performance.py` | Season stats, rolling form, radar percentiles | Player reviews, recruitment |
| `xg_model.py` | Custom trainable xG model with evaluation | Model understanding, custom features |
| `xg_model_advanced.py` | Gradient boosting xG with hyperparameter tuning | Higher accuracy xG predictions |
| `similarity.py` | Cosine similarity on normalised player vectors | Recruitment shortlisting, replacement finding |
| `possession_chains.py` | Build-up sequence analysis, transition metrics | Tactical pattern identification |
| `set_pieces.py` | Corner/FK clustering, delivery zones, efficiency | Set-piece coaching & defence |
| `simulation.py` | Monte Carlo match/season outcome simulation | Pre-match strategy, projections |
| `development.py` | Multi-season trajectory analysis, breakout detection | Academy scouting, squad planning |
| `spatial.py` | Voronoi tessellation, passing lanes, coverage gaps | Space control, defensive analysis |
| `video_alignment.py` | Event-to-video sync, clip generation, SRT export | Coach video review workflow |
| `tracking.py` | Pitch control, physical metrics, space analysis | Advanced tactical analysis (with tracking data) |
| `visualisations.py` | Shot maps, passing networks, heatmaps, xG timeline | Reports, presentations, dashboards |
| `cache.py` | Parquet-based query result caching | Fast notebook/dashboard iteration |
| `pdf_report.py` | Automated PDF/HTML reports | Coach presentations, weekly reports |
| `api.py` | FastAPI REST endpoints with Pydantic validation | External integrations, mobile apps |

## Dashboard

A custom React + TypeScript analytics dashboard built for performance analysts, deployed on **GitHub Pages**.

**Stack**: React 19, TypeScript 6, Vite 8, Tailwind CSS 4, D3.js, Recharts, TanStack Query

**Live**: `https://<username>.github.io/MatchMind/`

### Pages

1. **Dashboard** — Overview with data availability status and navigation to all modules
2. **Opponent Profile** — Scouting report with attack patterns, defensive shape, key player threats
3. **Player Performance** — Individual season summary, rolling form chart, radar percentiles, squad comparison
4. **Team Scorecard** — KPI cards, possession style breakdown, defensive zone analysis, set-piece efficiency
5. **Match Analysis** — Shot map (D3 pitch), xG timeline, passing network, pressure heatmap (canvas + KDE)
6. **Player Comparison** — Side-by-side similarity search for recruitment shortlisting
7. **Simulation** — Monte Carlo match outcome prediction with scoreline distribution chart

### Features

- Dark/light theme with Premier League-inspired colour palette
- Responsive sidebar navigation with collapsible menu
- Custom SVG football pitch rendering (StatsBomb 120×80 coordinates)
- Canvas-based pressure heatmaps with kernel density estimation
- Sortable data tables with per-90 metrics
- Loading skeletons and error states throughout
- Client-side routing compatible with GitHub Pages (SPA redirect via 404.html)

### Running Locally

```bash
# From project root
npm run dev
# → http://localhost:5173

# Or from frontend/ directly
cd frontend && npm run dev
```

## Report Generation

Generate coach-ready PDF reports from the command line:

```bash
# Post-match report
uv run fb-report --type match --match-id 3869685

# Opponent scouting document
uv run fb-report --type opponent --team-id 771 --season-id 106

# Player profile
uv run fb-report --type player --player-id 5503 --season-id 106
```

Reports are saved to `data/reports/` as PDF (with WeasyPrint) or HTML fallback.

## Performance

See [docs/PERFORMANCE.md](docs/PERFORMANCE.md) for full profiling results.

Key wins:
- **70x query speedup** via composite indexes matching analytical query patterns
- **5-10x faster ingestion** via PostgreSQL COPY protocol (staging table + upsert)
- **3-4x faster downloads** via async concurrent fetching (httpx, concurrency=8)
- **50ms data access** via Parquet cache layer (vs 800ms from PostgreSQL)
- **Sub-second frontend** — TanStack Query with 5-min staleTime, code splitting, lazy routes
- **Vectorised Python** — pandas operations replace row-level loops throughout
- **Connection pooling** — Reuse connections across API endpoints

## Video Integration

See [docs/VIDEO_INTEGRATION.md](docs/VIDEO_INTEGRATION.md) for the full guide on:
- Synchronising StatsBomb event timestamps with broadcast video
- Extracting tactical clips with FFmpeg
- Tagging clips with analytical context
- Integrating clips into the dashboard

## Custom xG Model

The project includes multiple xG models:

```python
from football_analytics.analysis.xg_model import train_xg_model
from football_analytics.analysis.xg_model_advanced import train_advanced_xg_model, compare_models

# Baseline model
baseline, metrics, cv_probs = train_xg_model(shots_df)
print(metrics.summary())
# Brier Score: 0.0712 | ROC-AUC: 0.782

# Advanced model (gradient boosting with hyperparameter tuning)
result = train_advanced_xg_model(shots_df, backend="hist", tune_hyperparams=True)
print(result.metrics.summary())
# Brier Score: 0.0648 | ROC-AUC: 0.821

# Compare models
comparison = compare_models(shots_df, baseline, result.model)
```

## Match Simulation

Monte Carlo simulation for match outcome prediction:

```python
from football_analytics.analysis.simulation import simulate_match, format_simulation_report

result = simulate_match(home_xg=1.8, away_xg=1.2, home_team="Arsenal", away_team="Chelsea")
print(format_simulation_report(result))
# Arsenal win: 48.2% | Draw: 24.1% | Chelsea win: 27.7%
# Most likely score: 2-1 | Over 2.5: 58.3% | BTTS: 62.1%
```

## Possession Chain Analysis

Analyse build-up patterns and dangerous possessions:

```python
from football_analytics.analysis.possession_chains import (
    extract_possession_chains, chains_to_dataframe, compute_team_possession_profile
)

chains = extract_possession_chains(events_df)
chains_df = chains_to_dataframe(chains)
profile = compute_team_possession_profile(chains_df, team_id=771)
# → style_distribution, box_entry_rate, xg_per_chain, transition metrics
```

## REST API

Launch the FastAPI server (serves data to the React frontend and external integrations):

```bash
uv run fb-api
# → API docs at http://localhost:8080/docs

# Example: predict xG
curl -X POST http://localhost:8080/api/v1/xg/predict \
  -H "Content-Type: application/json" \
  -d '{"location_x": 105, "location_y": 40, "shot_body_part": "Foot"}'

# Example: simulate match
curl -X POST http://localhost:8080/api/v1/simulation/match \
  -H "Content-Type: application/json" \
  -d '{"home_xg": 1.8, "away_xg": 1.2, "home_team": "Liverpool", "away_team": "Everton"}'
```

See [docs/API_GUIDE.md](docs/API_GUIDE.md) for the full endpoint reference.

## Player Similarity

Find similar players for recruitment or tactical replacement:

```python
from football_analytics.analysis.similarity import compute_player_vectors, find_similar_players

vectors = compute_player_vectors(season_id=106, engine=engine)
similar = find_similar_players(target_player_id=5503, player_vectors=vectors, position_group="FW")
```

## Development

```bash
# Install all dependencies (Python + frontend)
uv sync --all-extras
npm run install:frontend

# Run linter
uv run ruff check src/ tests/

# Run type checker
uv run mypy src/football_analytics/

# Run backend tests with coverage
uv run pytest --cov-report=html

# Format code
uv run ruff format src/ tests/

# Frontend type-check + lint
npm run type-check
npm run lint

# Production build (outputs to frontend/dist/)
npm run build
```

## Data Source

This project uses [StatsBomb Open Data](https://github.com/statsbomb/open-data) — freely available event-level football data under a non-commercial license. No proprietary data is included.

Default dataset: **FIFA World Cup 2022** (competition_id=43, season_id=106).

## Documentation

### For Users
- **[API Guide](docs/API_GUIDE.md)** — Complete REST API reference with endpoint examples, error handling, integration patterns
- **[Video Integration](docs/VIDEO_INTEGRATION.md)** — How to sync events with broadcast video and extract clips
- **[Technical Appendix](docs/TECHNICAL_APPENDIX.md)** — Detailed methodology for all metrics, models, and analyses

### For Developers
- **[Testing Guide](docs/TESTING_GUIDE.md)** — Test organization (73 tests), running tests, writing new tests, coverage targets
- **[PERFORMANCE.md](docs/PERFORMANCE.md)** — Profiling results, optimisation strategies, benchmarks

## License

MIT — see [LICENSE](./LICENSE).
