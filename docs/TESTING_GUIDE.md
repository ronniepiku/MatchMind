# Testing Guide

## Overview

MatchMind uses **pytest** for comprehensive unit and integration testing. Tests are organized by module with shared fixtures in `conftest.py`.

## Test Structure

```
tests/
├── conftest.py                          # Shared fixtures (39 fixture definitions)
├── unit/
│   ├── test_ingest.py                   # Data ingestion pipeline (10 tests)
│   ├── test_cache.py                    # Parquet caching (2 tests)
│   ├── test_api.py                      # FastAPI REST endpoints (6 tests)
│   └── analysis/
│       ├── test_visualizations.py       # Shot maps, xG timeline (3 tests)
│       ├── test_xg_models.py            # Basic + advanced xG (7 tests)
│       ├── test_similarity.py           # Player similarity engine (6 tests)
│       ├── test_tracking.py             # Tracking data integration (7 tests)
│       ├── test_possession_chains.py    # Possession sequence analysis (6 tests)
│       ├── test_set_pieces.py           # Set-piece analysis (2 tests)
│       ├── test_simulation.py           # Monte Carlo match simulation (5 tests)
│       ├── test_development.py          # Player development tracking (3 tests)
│       ├── test_spatial.py              # Voronoi, coverage analysis (5 tests)
│       ├── test_video_alignment.py      # Event-to-video sync (4 tests)
│       ├── test_opponent_profile.py     # Opponent scouting (3 tests)
│       └── test_player_performance.py   # Player metrics & radar (4 tests)
└── __init__.py
```

**Total: 73 tests across 15 test modules**

## Running Tests

### Run all tests
```bash
uv run pytest
```

### Run with coverage report
```bash
uv run pytest --cov=src/football_analytics --cov-report=html
# Open htmlcov/index.html in browser
```

### Run specific test file
```bash
uv run pytest tests/unit/test_ingest.py
```

### Run specific test class
```bash
uv run pytest tests/unit/analysis/test_xg_models.py::TestXGModel
```

### Run specific test function
```bash
uv run pytest tests/unit/analysis/test_xg_models.py::TestXGModel::test_train_model_returns_pipeline
```

### Run with verbose output
```bash
uv run pytest -v
```

### Run with detailed failure info
```bash
uv run pytest --tb=long
```

### Run tests matching pattern
```bash
uv run pytest -k "xg"  # Runs all tests with "xg" in name
```

### Run in parallel (faster)
```bash
uv run pytest -n auto  # Requires pytest-xdist
```

## Test Categories

### 1. **Data Ingestion** (`tests/unit/test_ingest.py`)
- Event normalisation and coordinate extraction
- Lineup parsing and player detection
- StatsBomb raw data handling

**Key fixtures**: `sample_raw_events`, `sample_lineups`

### 2. **Caching** (`tests/unit/test_cache.py`)
- Parquet cache hit/miss behavior
- Cache invalidation
- Query result persistence

### 3. **Visualisations** (`tests/unit/analysis/test_visualizations.py`)
- Shot map generation (matplotlib)
- Interactive xG timeline (Plotly)
- Empty data handling

**Key fixtures**: `sample_shots_df`

### 4. **xG Models** (`tests/unit/analysis/test_xg_models.py`)
- Feature engineering (distance, angle, pressure, etc.)
- Basic logistic regression model training
- Advanced gradient boosting model
- Cross-validation and calibration
- Prediction bounds checking

**Key fixtures**: `sample_shots`

### 5. **Player Similarity** (`tests/unit/analysis/test_similarity.py`)
- Cosine similarity scoring
- Feature normalization
- Top-N player ranking
- Position-aware matching

**Key fixtures**: `player_vectors`

### 6. **Tracking Data** (`tests/unit/analysis/test_tracking.py`)
- StatsBomb ↔ Tracking coordinate conversion
- Pitch control calculation
- Physical metrics (distance, speed, acceleration)
- Team shape metrics (compactness, width, length)

### 7. **Possession Chains** (`tests/unit/analysis/test_possession_chains.py`)
- Chain extraction from event sequences
- Outcome classification (goal, shot, turnover)
- Build-up style identification (short pass, counter, wing play, etc.)
- xG accumulation
- Possession profile computation

**Key fixtures**: `sample_possession_events`

### 8. **Set-Pieces** (`tests/unit/analysis/test_set_pieces.py`)
- Corner/free-kick extraction
- Delivery zone classification
- Set-piece efficiency metrics

### 9. **Match Simulation** (`tests/unit/analysis/test_simulation.py`)
- Poisson-based outcome probabilities
- Win/draw/loss calculation
- Scoreline distribution
- In-match simulation
- xG → probability correlation

### 10. **Player Development** (`tests/unit/analysis/test_development.py`)
- Multi-season trajectory analysis
- Trend detection (improving/declining/stable)
- Breakout candidate identification
- Age curve computation

### 11. **Spatial Analysis** (`tests/unit/analysis/test_spatial.py`)
- Voronoi tessellation
- Passing lane availability
- Defensive coverage gap detection
- Team compactness metrics
- Progressive event identification

### 12. **Video Alignment** (`tests/unit/analysis/test_video_alignment.py`)
- Event → timecode conversion
- Timestamp offset calibration
- FFmpeg command generation
- SRT subtitle export

### 13. **API Endpoints** (`tests/unit/test_api.py`)
- Health check endpoint
- xG prediction endpoint
- Match simulation endpoint
- CORS configuration
- OpenAPI documentation availability

### 14. **Opponent Profile** (`tests/unit/analysis/test_opponent_profile.py`)
- Attack pattern analysis
- Defensive shape estimation
- Key threat identification

### 15. **Player Performance** (`tests/unit/analysis/test_player_performance.py`)
- Season summary metrics
- Rolling form calculation
- Squad comparison
- Radar chart data generation

## Shared Fixtures (`conftest.py`)

### Ingest Fixtures
- `sample_raw_events`: StatsBomb-like event DataFrame
- `sample_lineups`: Nested lineup dict structure

### Analysis Fixtures
- `sample_shots_df`: Shot data for visualisation
- `sample_shots`: Extended shot data for xG model training (120 rows)
- `player_vectors`: 20 players with per-90 statistics
- `sample_possession_events`: 2 possession sequences with passes and shots

## Writing New Tests

### Test template
```python
import pytest
import pandas as pd

class TestNewModule:
    """Tests for new_module.py functionality."""
    
    @pytest.fixture
    def setup_data(self) -> pd.DataFrame:
        """Create test data."""
        return pd.DataFrame([...])
    
    def test_basic_functionality(self, setup_data: pd.DataFrame) -> None:
        """Should do X given Y."""
        from module_to_test import function_to_test
        
        result = function_to_test(setup_data)
        assert result is not None
        assert isinstance(result, dict)
    
    def test_edge_case_empty_input(self) -> None:
        """Should handle empty input gracefully."""
        from module_to_test import function_to_test
        
        empty_df = pd.DataFrame(columns=[...])
        result = function_to_test(empty_df)
        assert result is not None
    
    def test_raises_on_invalid_input(self) -> None:
        """Should raise ValueError for invalid input."""
        from module_to_test import function_to_test
        
        with pytest.raises(ValueError):
            function_to_test(invalid_data)
```

### Best practices
1. **Use fixtures** — Define reusable test data in `conftest.py` or class
2. **Test edge cases** — Empty inputs, None values, large datasets
3. **Use parametrize** — For testing multiple input scenarios
4. **Clear test names** — `test_<function>_<scenario>` pattern
5. **One assertion per test** — Or group related assertions with comments
6. **Use pytest.approx** — For floating-point comparisons

## Continuous Integration

Tests run on every push via GitHub Actions (`.github/workflows/ci.yml`):

```yaml
- Install dependencies (uv sync)
- Run pytest with coverage
- Generate coverage report
- Upload to Codecov (if configured)
```

## Coverage Targets

| Module | Target | Current* |
|--------|--------|----------|
| ingest.py | 90% | ~85% |
| analysis/*.py | 80% | ~75% |
| api.py | 85% | ~70% |
| cache.py | 90% | ~80% |

*Approximate based on last full run

## Troubleshooting

### Tests fail with "ModuleNotFoundError"
```bash
# Ensure dependencies are installed
uv sync
```

### Tests timeout
```bash
# Increase timeout for slow tests
uv run pytest --timeout=60
```

### Database connection errors in tests
- Tests requiring DB should use mocks or fixtures
- Check `.env` for test DB configuration
- Some tests may be skipped if DB unavailable

### Flaky tests (inconsistent failures)
- Avoid hardcoding random seeds in fixtures
- Use `pytest-xdist` for parallel testing
- Isolate test data between runs

## Debugging Tests

### Print debug info
```python
import pytest

def test_something(capsys):
    print("Debug message")
    captured = capsys.readouterr()
    assert "message" in captured.out
```

### Drop into debugger
```python
def test_something():
    import pdb; pdb.set_trace()
    # Code stops here, inspect variables
```

### Run single test with verbose output
```bash
uv run pytest tests/unit/test_cache.py::TestParquetCache::test_cache_miss_then_hit -vv -s
```

## Extending Test Suite

### To add tests for a new module:
1. Create `tests/unit/analysis/test_<module>.py` (or `tests/unit/test_<module>.py`)
2. Add shared fixtures to `tests/conftest.py` if needed
3. Write test classes following naming convention: `Test<ModuleClass>`
4. Run tests: `uv run pytest tests/unit/analysis/test_<module>.py -v`
5. Check coverage: `uv run pytest --cov=src/football_analytics/analysis/<module>`

### To add a fixture:
1. Open `tests/conftest.py`
2. Add `@pytest.fixture` decorator
3. Implement fixture function returning test data
4. Use in tests: `def test_name(fixture_name):`

## Useful pytest plugins

```bash
# Install additional testing tools
uv add --dev pytest-cov pytest-xdist pytest-timeout pytest-mock

# Run with them
uv run pytest --cov --timeout=30 -n auto
```

## References

- **pytest documentation**: https://docs.pytest.org
- **pytest fixtures**: https://docs.pytest.org/fixture.html
- **pytest parametrize**: https://docs.pytest.org/parametrize.html
- **pytest-cov**: https://pytest-cov.readthedocs.io
