# Changelog

All notable changes to this project will be documented in this file.

## [0.5.1] — 2026-06-03

### Changed — Architecture Refactoring

- **Split monolithic `api.py`** (~2600 lines) into 7 domain-specific route modules under `src/football_analytics/routes/`:
  - `health.py` — Health probes, readiness checks
  - `analysis.py` — xG prediction, player profiles, team analysis
  - `dashboard.py` — Frontend data queries (teams, seasons, matches)
  - `prediction.py` — Match prediction, ML pipeline, ratings
  - `matchday.py` — Fixtures, calendar, pre/post match
  - `executive.py` — Executive reports, ad-hoc SQL queries
  - `cache.py` — Cache stats, system validation
- **Slim `api.py`**: Now ~140 lines handling only app setup (lifespan, middleware, CORS, exception handling)
- **Rate limiting**: Added slowapi with 60 req/min default limit
- **Security header**: Replaced deprecated `X-XSS-Protection` with `Content-Security-Policy`
- **Request ID middleware**: All responses include `X-Request-ID` for tracing
- **Consolidated `normalise_database_url()`**: Single utility in `config.py` (used by api.py, alembic/env.py)
- **Consolidated model version**: Single source of truth in `prediction/ml_pipeline.py`, re-exported through `prediction/__init__.py`
- **Fixed DB name default**: Standardized to "MatchMind" (was "football_analytics" in some places)

### Fixed

- `api.py`: `model_version` field was set to `metrics.n_matches` instead of the actual version string
- `api.py`: `_MODELS_DIR` imported as variable but was a function (`_get_models_dir()`)
- `cache.py`: Fixed type annotation `CACHE_DIR: Path | None = None`
- `ingest_orchestrator.py`: Fixed f-string in `logger.info()` call (used `%s` format correctly)
- Removed duplicate `/system/health/db` endpoint (functionality merged into `/api/v1/ready`)

### Changed — Dependencies

- Moved heavy dependencies to optional groups in `pyproject.toml`:
  - `notebooks` extra: jupyter, nbformat
  - `viz` extra: matplotlib, mplsoccer
  - `reports` extra: weasyprint, matplotlib, mplsoccer
- Removed from core dependencies: dash, dash-bootstrap-components, jupyter, nbformat, matplotlib, mplsoccer, weasyprint

### Removed

- `src/football_analytics/dashboard/` — Removed (frontend is React on GitHub Pages)
- `fb-dashboard` script entry point
- Dead files: `analysis/xg_model_selection.py`, `prediction/model_versioning.py` duplicate logic

---

## [0.5.0] — 2026-06-03

### Added — Prediction Engine (Phase 1)

- **Match predictor** (`prediction/match_predictor.py`): Dixon-Coles model with exponential decay, home advantage factors, and multi-format prediction output (probabilities, scores, markets)
- **Team rating system** (`prediction/team_rating.py`): Bayesian ELO-style ratings with offensive/defensive decomposition, form weighting, and confidence intervals
- **Tactical matchup analysis** (`prediction/tactical_matchup.py`): Style-based head-to-head assessment with pressing resistance, build-up compatibility, and set-piece vulnerability scoring
- **Tournament simulation** (`prediction/tournament.py`): Monte Carlo tournament progression (supports group stages, knockouts, seeded draws) with team qualification probabilities
- **Model versioning** (`prediction/model_versioning.py`): Prediction accuracy tracking with Brier score calculation, calibration analysis, rolling accuracy dashboards

### Added — Matchday Operations (Phase 2)

- **Fixture management** (`matchday/fixtures.py`): Competition-aware fixture calendar with status lifecycle (scheduled → preview → in-progress → completed → reviewed)
- **Pre-match packs** (`matchday/pre_match.py`): Automated analyst-ready dossiers combining opponent profile, prediction, tactical suggestions, and key threats
- **Post-match processing** (`matchday/post_match.py`): Automated result ingestion, actual-vs-predicted comparison, xG narrative, and performance flags
- **Match reviews** (`matchday/reviews.py`): Structured post-match review workflows with tactical observations, player ratings, and lesson extraction

### Added — Executive Reporting (Phase 3)

- **Executive intelligence** (`reports/executive.py`): RAG traffic-light reporting (weekly briefings, player assessments, competition outlooks, post-match summaries) designed for Director of Football / Board consumption
- 4 new API endpoints: `/executive/weekly-briefing`, `/executive/player-assessment`, `/executive/competition-outlook`, `/executive/post-match-summary`

### Added — Ad-Hoc Analysis Toolkit (Phase 4)

- **Parameterised query library** (`analysis/queries.py`): 21 production-grade SQL queries across 8 categories (Pressing, Build-Up, Chance Creation, Defence, Set Pieces, Scouting, H2H, Form). All parameterised to prevent injection
- 2 new API endpoints: `GET /analysis/queries` (catalogue), `POST /analysis/query` (execution)

### Added — Data Infrastructure (Phase 5)

- **Ingestion orchestrator** (`ingest_orchestrator.py`): Multi-competition incremental sync with delta detection, competition registry, and CLI interface
- **Database migrations** (`alembic/`): Alembic integration with environment-aware configuration. Initial migration includes all schema + v0.5.0 additions
- **Data validation pipeline** (`validation.py`): 7-check quality gate (schema, event types, coordinates, xG bounds, temporal order, null rates, duplicates) with DB-persisted audit trail
- **Railway deployment support**: `railway.toml`, `DATABASE_URL` support in config, health check endpoints, production Dockerfile with auto-migrations

### Added — Frontend Pages

- **Predictions page** (`pages/Predictions.tsx`): Match predictor form, team ratings table, tournament simulation tab
- **Matchday Calendar** (`pages/MatchdayCalendar.tsx`): Fixture timeline with status indicators, pre-match pack generation, recent results
- **Analysis Workbench** (`pages/AnalysisWorkbench.tsx`): Category-filtered query selector, parameter forms, interactive results table with CSV export
- **Typed API layer** (`api/endpoints.ts`, `api/types.ts`): Full TypeScript types and fetch functions for all new backend endpoints
- Sidebar navigation updated with Brain, Calendar, FlaskConical icons

### Added — System Endpoints

- `GET /api/v1/cache/stats` — Parquet cache statistics
- `POST /api/v1/cache/invalidate` — Cache invalidation by name
- `GET /api/v1/system/health/db` — Deep database connectivity check
- `GET /api/v1/system/validation/{match_id}` — On-demand data quality validation

### Changed

- `config.py`: Supports `DATABASE_URL` environment variable (Railway/Heroku style) with automatic `postgres://` → `postgresql+psycopg2://` rewrite
- `Dockerfile`: Multi-stage build with health checks, auto-migration on startup, non-root user, Railway `PORT` support
- `.github/workflows/ci.yml`: Added lint, typecheck, security audit, and frontend build jobs alongside existing test matrix
- `.env.example`: Extended with cache, validation, ingestion, and Railway configuration variables
- `pyproject.toml`: Version 0.5.0, alembic already in dependencies

### Added — Testing

- `tests/test_executive.py` (17 tests): RAG status, dataclass structure, report generation with mocked DB
- `tests/test_queries.py` (11 tests): Query catalogue, category filtering, parameter validation, execution
- `tests/test_infra.py` (11 tests): Competition registry, ingestion orchestrator, model versioning
- Full suite: 180 tests passing

---

## [0.4.0] — 2026-05-20

### Added — Frontend Dashboard

- **React + TypeScript frontend** (`frontend/`): Complete replacement of Plotly Dash with a custom-built, production-grade analytics dashboard deployed on GitHub Pages.
  - React 19, TypeScript 6, Vite 8, Tailwind CSS 4
  - D3.js custom football pitch visualisations (StatsBomb 120×80 coordinates)
  - Recharts for standard chart types (line, bar, pie)
  - TanStack Query for server state with 5-min staleTime
  - Dark/light theme system with Premier League-inspired colour palette
  - Canvas-based pressure heatmaps with kernel density estimation
  - Custom SVG player radar charts
  - 7 pages: Dashboard, Opponent Profile, Player Performance, Team Scorecard, Match Analysis, Player Comparison, Simulation
  - Client-side routing via React Router v7 with GitHub Pages SPA compatibility

### Added — CI/CD

- **GitHub Pages deployment** (`.github/workflows/deploy-frontend.yml`): Automatic frontend deployment on push to main
- **Root `package.json`**: Convenience scripts (`npm run dev`, `npm run build`) that delegate to `frontend/`

### Changed

- `src/football_analytics/api.py`: Expanded API with new endpoints for frontend consumption (`/teams`, `/seasons`, `/players`, `/matches`, `/data-availability`, `/opponent/report`, `/player/summary`, `/player/rolling-form`, `/player/radar`, `/player/squad-comparison`, `/team/scorecard`, `/match/shots`, `/match/xg-timeline`, `/match/passing-network`, `/match/pressure-map`, `/player/similar`). Updated CORS origins.
- `README.md`: Rewritten to reflect React frontend architecture, updated Quick Start, project structure, and Dashboard sections
- `docs/API_GUIDE.md`: Updated to reference frontend as primary API consumer
- `docs/PERFORMANCE.md`: Replaced Dash-specific optimisations with frontend layer (TanStack Query, code splitting)
- `docs/TECHNICAL_APPENDIX.md`: Updated component references

### Removed

- `src/football_analytics/dashboard/` — Legacy Plotly Dash application (replaced by `frontend/`)

---

## [0.3.0] — 2026-05-15

### Added — Analysis Modules

- **Possession chain analysis** (`analysis/possession_chains.py`): Extract, classify, and analyse possession sequences. Identifies build-up styles (short passing, wing play, counter-attack, set piece), computes chain outcomes (goal, shot, turnover), and provides team possession profiles with transition metrics.
- **Set-piece analysis** (`analysis/set_pieces.py`): Corner kick and free kick extraction, delivery zone classification (near/far post, penalty spot, edge of box), outcome tracking, efficiency metrics, hierarchical clustering for routine identification, and defensive vulnerability analysis.
- **Advanced xG model** (`analysis/xg_model_advanced.py`): Gradient boosting upgrade (HistGradientBoosting with sklearn fallback). Features interaction terms (distance×angle, pressure×header), hyperparameter tuning via GridSearchCV, isotonic calibration, and model comparison utilities. Expected AUC improvement: 0.78 → 0.82.
- **Player development tracking** (`analysis/development.py`): Multi-season longitudinal analysis computing per-90 metrics, trend slopes, trajectory classification (improving/declining/breakout/stable), breakout candidate identification, and age curve computation with confidence intervals.
- **Monte Carlo match simulation** (`analysis/simulation.py`): Poisson-based match outcome simulation (10K+ iterations). Provides win/draw/loss probabilities, scoreline distributions, over/under thresholds, BTTS, minute-by-minute probability evolution, in-match remaining-time simulation, and full season projections.
- **Spatial dominance maps** (`analysis/spatial.py`): Voronoi tessellation for space control analysis, passing lane availability assessment, defensive coverage gap identification, team compactness metrics (convex hull area, spread), and progressive event detection from event data.
- **Video timestamp alignment** (`analysis/video_alignment.py`): Event-to-broadcast video synchronisation with configurable offsets, automatic calibration from reference events, FFmpeg clip extraction script generation, SRT subtitle export, and full event timeline generation with timecodes.

### Added — Infrastructure

- **FastAPI REST API** (`api.py`): Full REST layer with Pydantic request/response models. Endpoints for xG prediction, match simulation, player profiles, and health checks. CORS enabled. Auto-generated OpenAPI docs at `/docs`.
- **Table partitioning** (`db/partitioning.sql`): Events table partitioned by `season_id` using PostgreSQL range partitioning. Includes migration function, dynamic partition creation, and propagated indexes.
- **New CLI command**: `fb-api` to launch the FastAPI server.

### Added — Testing

- `tests/test_v030_enhancements.py`: Comprehensive test suite covering possession chains (extraction, outcomes, styles, profiles), set pieces (extraction, efficiency), advanced xG (features, training, prediction), match simulation (probabilities, in-match, reporting), player development (profiles, trends), spatial analysis (Voronoi, coverage, passing lanes, compactness), video alignment (timecodes, clips, calibration, FFmpeg/SRT export), and API endpoints (health, xG prediction, simulation, validation).

### Changed

- `pyproject.toml`: Version bump to 0.3.0. Added fastapi, uvicorn, pydantic dependencies. New `fb-api` script.
- `README.md`: Fully updated with all new modules, usage examples, and project structure.
- `__init__.py`: Version 0.3.0.

### Added — Analysis Modules

- **Custom xG model** (`analysis/xg_model.py`): Trainable logistic regression with feature engineering (distance, angle, body part, pressure, penalties). Includes cross-validated evaluation (Brier score, ROC-AUC, log loss) and StatsBomb comparison utility.
- **Player similarity engine** (`analysis/similarity.py`): Position-aware cosine similarity on normalised per-90 feature vectors. Supports recruitment shortlisting and tactical replacement finding.
- **Tracking data integration** (`analysis/tracking.py`): Adapters for Metrica/EPTS formats, event-tracking synchronisation, simplified pitch control model, physical metrics calculation, and team shape analysis.

### Added — Reports & Outputs

- **Automated PDF reports** (`reports/pdf_report.py`): Match reports, opponent scouting documents, and player profiles generated via Jinja2 templates + WeasyPrint. HTML fallback when WeasyPrint unavailable.
- **Report templates**: Three professional HTML/CSS templates for match, opponent, and player reports.
- **New CLI command**: `fb-report --type {match|opponent|player}`

### Added — Testing

- `tests/test_enhancements.py`: Comprehensive test suite covering xG model training/prediction, player similarity scoring, Parquet cache hit/miss/invalidation, coordinate conversions, pitch control, and physical metrics.

### Changed

- `pyproject.toml`: Version bump to 0.2.0. Added httpx, jinja2, weasyprint, pytest-asyncio dependencies.
- `schema.sql`: Added materialised views with refresh function.
- `ingest.py`: Refactored `bulk_load_events` to use COPY protocol with fallback.
- `.github/workflows/ci.yml`: Updated for new test files.
- Documentation updated across README, PERFORMANCE.md, TECHNICAL_APPENDIX.md.

## [0.1.0] — 2026-05-15

### Added — Initial Release

- Data ingestion pipeline (statsbombpy → PostgreSQL)
- Database schema with performance indexes and analytical views
- Opponent profiling module (attack patterns, defensive shape, key players)
- Player performance module (season summary, rolling form, radar percentiles)
- Visualisations (shot maps, passing networks, pressing heatmaps, xG timeline)
- Interactive Plotly Dash dashboard (2 views)
- Jupyter notebook with WC 2022 Final analysis
- Video integration HOWTO documentation
- Docker + docker-compose setup
- GitHub Actions CI pipeline
- MIT license
