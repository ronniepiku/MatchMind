# MatchMind - A football analytics Platform

[![CI](https://github.com/YOUR_USERNAME/football-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/ronniepiku/MatchMind/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

Match Mind is a **Production-grade football data analysis pipeline**. From raw StatsBomb event data to actionable tactical insights, interactive dashboards, automated PDF reports, Monte Carlo match simulation, and coaching-ready presentations.

## Key Features

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
- **FastAPI REST layer**: Full API for external integrations (Tableau, mobile, Slack bots)
- **Interactive dashboard**: Plotly Dash with opponent scouting and player performance views
- **Automated PDF reports**: Match reports, opponent scouts, and player profiles via Jinja2 + WeasyPrint
- **Parquet cache layer**: Instant notebook/dashboard loads bypassing database for read-heavy workflows
- **Materialised views**: Pre-computed SQL aggregates refreshed after each ingestion
- **Table partitioning**: Event table partitioned by season_id for scalable query performance
- **Performance-optimised**: Indexed queries (70x speedup), COPY protocol (5-10x), async I/O (3-4x)
- **Production engineering**: Type hints, unit tests, CI/CD, Docker, modular package structure

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- PostgreSQL 14+ (or use Docker Compose)

### Setup

```bash
# Clone the repo
git clone https://github.com/ronniepiku/MatchMind.git
cd football-analytics

# Install dependencies with uv
uv sync

# Start PostgreSQL (via Docker)
docker compose up -d db

# Configure environment
cp .env.example .env  # Edit credentials if needed

# Ingest sample data (3 matches for quick demo)
uv run fb-ingest --max-matches 3

# Or use async ingestion (3-4x faster for full datasets)
uv run fb-ingest-async --max-matches 3

# Run tests
uv run pytest

# Launch dashboard
uv run fb-dashboard
# → Open http://localhost:8050

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
uv run fb-dashboard
```

### Full Docker Environment

```bash
docker compose up --build
# Dashboard: http://localhost:8050
# Postgres: localhost:5432
```

## Project Structure

```
football-analytics/
├── src/football_analytics/
│   ├── __init__.py              # Package root (v0.3.0)
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
│   ├── dashboard/
│   │   └── app.py               # Plotly Dash application
│   └── reports/
│       ├── pdf_report.py        # Automated PDF generation
│       └── templates/           # Jinja2 HTML report templates
├── tests/                       # Unit tests (pytest)
│   ├── test_ingest.py           # Ingestion tests
│   ├── test_analysis.py         # Visualisation tests
│   ├── test_enhancements.py     # xG model, similarity, cache, tracking tests
│   └── test_v030_enhancements.py # v0.3 module tests (chains, simulation, API)
├── notebooks/                   # Reproducible Jupyter analyses
├── docs/                        # Technical docs
│   ├── PERFORMANCE.md           # Profiling results & optimisation notes
│   ├── VIDEO_INTEGRATION.md     # Video sync & clip extraction guide
│   └── TECHNICAL_APPENDIX.md    # Methods, metrics, assumptions
├── data/                        # Raw + processed + cache (gitignored)
├── .github/workflows/ci.yml     # GitHub Actions CI
├── Dockerfile                   # Container build
├── docker-compose.yml           # Full stack orchestration
├── pyproject.toml               # Dependencies (uv/hatch)
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

Two interactive views accessible at `http://localhost:8050`:

1. **Opponent Profile** — Select a team and season to generate a scouting report with attack pattern breakdown, defensive zone analysis, and key player identification.
2. **Player Performance** — Individual player season summary, rolling form chart, and squad-level comparison table.

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
- **Instant dashboard loads** via materialised views (pre-computed aggregates)
- **50ms data access** via Parquet cache layer (vs 800ms from PostgreSQL)
- **Vectorised Python** — pandas operations replace row-level loops throughout
- **Connection pooling** — Reuse connections across dashboard callbacks

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

Launch the FastAPI server for external integrations:

```bash
uv run fb-api
# → API docs at http://localhost:8000/docs

# Example: predict xG
curl -X POST http://localhost:8000/api/v1/xg/predict \
  -H "Content-Type: application/json" \
  -d '{"location_x": 105, "location_y": 40, "shot_body_part": "Foot"}'

# Example: simulate match
curl -X POST http://localhost:8000/api/v1/simulation/match \
  -H "Content-Type: application/json" \
  -d '{"home_xg": 1.8, "away_xg": 1.2, "home_team": "Liverpool", "away_team": "Everton"}'
```

## Player Similarity

Find similar players for recruitment or tactical replacement:

```python
from football_analytics.analysis.similarity import compute_player_vectors, find_similar_players

vectors = compute_player_vectors(season_id=106, engine=engine)
similar = find_similar_players(target_player_id=5503, player_vectors=vectors, position_group="FW")
```

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run linter
uv run ruff check src/ tests/

# Run type checker
uv run mypy src/football_analytics/

# Run tests with coverage
uv run pytest --cov-report=html

# Format code
uv run ruff format src/ tests/
```

## Data Source

This project uses [StatsBomb Open Data](https://github.com/statsbomb/open-data) — freely available event-level football data under a non-commercial license. No proprietary data is included.

Default dataset: **FIFA World Cup 2022** (competition_id=43, season_id=106).

## License

MIT — see [LICENSE](./LICENSE).
