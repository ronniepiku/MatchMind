# MatchMind - A football analytics Platform

[![CI](https://github.com/ronniepiku/MatchMind/actions/workflows/ci.yml/badge.svg)](https://github.com/ronniepiku/MatchMind/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

MatchMind is a **production-grade football intelligence platform** designed for elite clubs. From raw StatsBomb event data to match predictions, automated matchday workflows, executive briefings, and ad-hoc analytical queries — all accessible through a React dashboard or REST API.

## Key Features

### Intelligence Layer
- **Match prediction engine**: Dixon-Coles model with team ratings, tactical matchup analysis, tournament simulation, and gradient-boosted ML predictions
- **Matchday operations**: Fixture calendar with status lifecycle, pre-match packs, post-match analysis, structured reviews
- **Executive reporting**: RAG traffic-light briefings, player assessments, competition outlooks (1-page max, plain language)
- **Ad-hoc analysis toolkit**: 21 parameterised SQL queries across 8 categories, accessible via API or React workbench

### Analytics Layer
- **Core analyses**: Opponent profiling, player performance, xG/xA, passing networks, pressing heatmaps
- **Custom xG model**: Logistic regression + gradient boosting with hyperparameter tuning (AUC ~0.82)
- **Player similarity engine**: Embedding-based comparison for recruitment shortlisting
- **Possession chains**: Sequence modelling of build-up patterns, transitions, and dangerous possessions
- **Set-piece analysis**: Corner/FK clustering, delivery zones, efficiency metrics
- **Match simulation**: Monte Carlo outcome prediction (10K iterations) with scoreline distributions
- **Spatial dominance**: Voronoi tessellation, passing lanes, defensive coverage gaps

### Infrastructure
- **React dashboard**: 9 tool pages with D3 pitch visualisations, dark/light theme, Tailwind CSS
- **FastAPI REST layer**: Modular route architecture, OpenAPI docs, CORS, cache endpoints, data validation
- **Database migrations**: Alembic with environment-aware config (local Postgres or Railway `DATABASE_URL`)
- **Data quality pipeline**: 7-check validation gate with audit trail
- **Parquet cache**: 50ms data access vs 800ms from PostgreSQL
- **Production deployment**: Railway-ready with Dockerfile, health checks, auto-migrations
- **CI/CD**: Lint + typecheck + test matrix + frontend build + security audit

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
createdb MatchMind
psql MatchMind < src/football_analytics/db/schema.sql

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
│   │   ├── api/                 # Typed HTTP client + endpoint functions
│   │   ├── components/          # Charts, layout, pitch, shared UI
│   │   ├── pages/               # Route-level pages
│   │   └── styles/              # Tailwind CSS + theme
│   └── vite.config.ts
├── src/football_analytics/
│   ├── config.py                # Environment settings (DATABASE_URL aware)
│   ├── api.py                   # FastAPI app setup (middleware, CORS, lifespan)
│   ├── routes/                  # API route modules (split by domain)
│   │   ├── health.py            # Health/readiness probes
│   │   ├── analysis.py          # xG, player profiles, team analysis
│   │   ├── dashboard.py         # Frontend data endpoints
│   │   ├── prediction.py        # Match prediction, ratings, ML pipeline
│   │   ├── matchday.py          # Fixtures, calendar, pre/post match
│   │   ├── executive.py         # Executive reports, ad-hoc queries
│   │   └── cache.py             # Cache stats, system endpoints
│   ├── ingest.py                # Sync ingestion (COPY protocol)
│   ├── async_ingest.py          # Async concurrent ingestion
│   ├── ingest_orchestrator.py   # Multi-competition incremental sync
│   ├── cache.py                 # Parquet cache layer
│   ├── validation.py            # Data quality pipeline (7 checks)
│   ├── db/
│   │   ├── schema.sql           # Full DDL + indexes + materialised views
│   │   ├── partitioning.sql     # Table partitioning by season
│   │   └── queries.sql          # Optimised analytical queries
│   ├── prediction/
│   │   ├── match_predictor.py   # Dixon-Coles match outcome model
│   │   ├── team_rating.py       # Bayesian team strength ratings
│   │   ├── tactical_matchup.py  # Style-based matchup analysis
│   │   ├── tournament.py        # Monte Carlo tournament simulation
│   │   ├── ml_pipeline.py       # Gradient-boosted ML match prediction
│   │   └── model_versioning.py  # Prediction accuracy tracking
│   ├── matchday/
│   │   ├── fixtures.py          # Fixture calendar & status lifecycle
│   │   ├── fixture_sync.py      # External fixture sync (football-data.org)
│   │   ├── pre_match.py         # Automated pre-match dossiers
│   │   ├── post_match.py        # Post-match result processing
│   │   └── reviews.py           # Structured match review workflow
│   ├── analysis/
│   │   ├── queries.py           # 21 parameterised analytical queries
│   │   ├── opponent_profile.py  # Opponent scouting reports
│   │   ├── player_performance.py
│   │   ├── possession_chains.py
│   │   ├── set_pieces.py
│   │   ├── simulation.py        # Monte Carlo match simulation
│   │   ├── spatial.py           # Voronoi + space control
│   │   └── ...                  # xG models, tracking, video, similarity
│   └── reports/
│       ├── executive.py         # Executive intelligence (RAG reports)
│       ├── pdf_report.py        # Automated PDF generation
│       └── templates/
├── alembic/                     # Database migrations
│   ├── env.py                   # Environment-aware (reads .env)
│   └── versions/                # Migration scripts
├── tests/                       # 180+ unit tests (pytest)
├── scripts/
│   └── run-ci-local.ps1         # Local CI runner
├── .github/workflows/
│   ├── ci.yml                   # Lint + typecheck + test + frontend + security
│   └── deploy-frontend.yml      # GitHub Pages deployment
├── Dockerfile                   # Production container (Railway-ready)
├── railway.toml                 # Railway deployment config
├── docker-compose.yml           # Local full-stack dev
└── pyproject.toml               # Python dependencies (uv/hatch)
```

## Analyses & Modules

| Module | Capability | Use Case |
|--------|-----------|----------|
| `prediction/match_predictor.py` | Dixon-Coles match outcome model | Pre-match win/draw/loss probabilities |
| `prediction/team_rating.py` | Bayesian team strength ratings | Power rankings, form tracking |
| `prediction/tournament.py` | Monte Carlo tournament simulation | Tournament progression probabilities |
| `matchday/pre_match.py` | Automated pre-match dossiers | Analyst workflow automation |
| `matchday/post_match.py` | Post-match result processing | Automated debrief data |
| `reports/executive.py` | RAG executive briefings | Board/DoF weekly updates |
| `analysis/queries.py` | 21 parameterised analytical queries | Ad-hoc tactical questions |
| `opponent_profile.py` | Attack patterns, defensive shape, key threats | Pre-match preparation |
| `player_performance.py` | Season stats, rolling form, radar percentiles | Player reviews, recruitment |
| `xg_model_advanced.py` | Gradient boosting xG with tuning | Higher accuracy xG predictions |
| `similarity.py` | Cosine similarity on normalised player vectors | Recruitment shortlisting |
| `possession_chains.py` | Build-up sequence analysis, transition metrics | Tactical pattern identification |
| `set_pieces.py` | Corner/FK clustering, delivery zones, efficiency | Set-piece coaching & defence |
| `simulation.py` | Monte Carlo match/season outcome simulation | Pre-match strategy, projections |
| `spatial.py` | Voronoi tessellation, passing lanes, coverage gaps | Space control analysis |
| `validation.py` | 7-check data quality pipeline | Data integrity before analytics |
| `cache.py` | Parquet-based query result caching | Fast notebook/dashboard loads |
| `api.py` + `routes/` | FastAPI REST endpoints (modular) | Frontend, integrations, mobile |

## Dashboard

A custom React + TypeScript analytics dashboard built for performance analysts, deployed on **GitHub Pages**.

**Stack**: React 19, TypeScript 6, Vite 8, Tailwind CSS 4, D3.js, Recharts, TanStack Query

**Live**: `https://<username>.github.io/MatchMind/`

### Pages

1. **Dashboard** — Overview with data availability status, navigation to all modules, and help tip for new users
2. **Predictions** — Match outcome predictor (Monte Carlo + ML), team ratings table, tournament simulation
3. **Matchday Calendar** — Fixture timeline with status lifecycle, pre-match pack generation
4. **Analysis Workbench** — Category-filtered query selector, parameter forms, results with CSV export
5. **Opponent Profile** — Scouting report with attack patterns, defensive shape, key player threats
6. **Player Performance** — Individual season summary, rolling form chart, radar percentiles, squad comparison
7. **Team Scorecard** — KPI cards, possession style breakdown, defensive zone analysis, set-piece efficiency
8. **Match Analysis** — Shot map (D3 pitch), xG timeline, passing network, pressure heatmap (canvas + KDE)
9. **Player Comparison** — Side-by-side similarity search for recruitment shortlisting

### Features

- Dark/light theme with Premier League-inspired colour palette
- Responsive sidebar navigation with collapsible menu
- In-page help panels on every tool page (click the Help icon for usage guidance)
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

# Install only optional groups you need
uv sync --extra notebooks   # Jupyter + nbformat
uv sync --extra viz          # matplotlib + mplsoccer
uv sync --extra reports      # WeasyPrint + matplotlib

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
- **[Testing Guide](docs/TESTING_GUIDE.md)** — Test organization (180+ tests), running tests, writing new tests, coverage targets
- **[Performance](docs/PERFORMANCE.md)** — Profiling results, optimisation strategies, benchmarks

### Deployment
- **[Railway Deployment](docs/DEPLOYMENT_RAILWAY.md)** — Full guide to deploy backend on Railway with managed PostgreSQL
- **[GitHub Pages](docs/DEPLOYMENT_GITHUB_PAGES.md)** — Deploy the React frontend as a static site

## License

MIT — see [LICENSE](./LICENSE).

## Disclaimer

MatchMind is for **educational and entertainment purposes only**. Predictions, simulations, and statistical outputs do not constitute gambling advice or betting recommendations. See [TERMS_OF_SERVICE.md](./TERMS_OF_SERVICE.md) for full terms.
