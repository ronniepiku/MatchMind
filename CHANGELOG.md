# Changelog

All notable changes to this project will be documented in this file.

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
