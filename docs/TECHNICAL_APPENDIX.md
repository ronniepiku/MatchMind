# Technical Appendix

## Methodology

### Data Source
- **StatsBomb Open Data**: Event-level football data at ~1500-3000 events per match
- **Coverage**: Selected competitions including FIFA World Cups, major European leagues
- **Granularity**: Individual actions (passes, shots, pressures, carries) with x/y coordinates on a 120×80 pitch

### Metrics Definitions

| Metric | Definition | Source |
|--------|-----------|--------|
| **xG (Expected Goals)** | Probability of a shot resulting in a goal, based on shot location, angle, body part, assist type, and game state | StatsBomb pre-computed model |
| **xA (Expected Assists)** | xG of the shot that a key pass creates | Derived from StatsBomb shot + pass data |
| **Pass Accuracy** | Completed passes / Total pass attempts | Computed from pass events |
| **Pressing Intensity** | Press actions per minute of opponent possession | Pressure events / opponent possession time |
| **Progressive Carries** | Ball carries that move ≥10m towards opponent goal | Carry events with location delta filter |
| **PPDA** | Passes per Defensive Action (opponent passes / team defensive actions in opponent half) | Computed from events in attacking half |

### xG Model Evaluation

#### StatsBomb Pre-Computed xG
StatsBomb's xG model is pre-computed and proprietary, but we can evaluate calibration:
- **Calibration**: Compare predicted goals (sum of xG) vs actual goals across a large sample
- **Expected metric**: Predicted ≈ Actual for well-calibrated model
- **Brier Score**: Mean squared difference between predicted probability and outcome (0/1)

```
For WC 2022: Sum(xG) = 157.3, Actual Goals = 172
Overperformance = +14.7 goals (expected at tournament level due to high stakes)
```

#### Custom xG Model (`analysis/xg_model.py`)

Our trainable logistic regression xG model provides:

| Feature | Engineering |
|---------|------------|
| Distance to goal | Euclidean from shot location to centre of goal |
| Shot angle | Angle subtended by the two goalposts from shot location |
| Body part | One-hot encoding (foot, head, other) |
| Under pressure | Binary flag from StatsBomb pressure data |
| Penalty | Binary flag for penalty kicks |
| Pitch zone | One-hot encoding of 6 zones (near/far × left/centre/right) |

**Evaluation metrics** (5-fold stratified cross-validation):
- **Brier Score**: ~0.07 (lower is better; random baseline = 0.25)
- **ROC-AUC**: ~0.78 (good discrimination between goals/misses)
- **Log Loss**: ~0.24 (well-calibrated probabilities)

**Comparison methodology**: `compare_to_statsbomb()` computes mean absolute difference between our model's predictions and StatsBomb's pre-computed xG values, establishing alignment with industry models.

### Player Similarity Methodology (`analysis/similarity.py`)

**Approach**: Position-aware cosine similarity on normalised feature vectors.

1. **Feature extraction**: Per-match metrics aggregated to per-90 rates
2. **Position filtering**: Only compare players in the same positional group
3. **Normalisation**: MinMaxScaler per feature (0-1 range within position group)
4. **Similarity**: Cosine similarity on normalised vectors (1 = identical profile, 0 = orthogonal)

**Key design decisions**:
- Per-90 normalisation removes playing time bias
- Position-aware filtering prevents comparing strikers to goalkeepers
- MinMax (not StandardScaler) ensures all features contribute equally regardless of distribution shape
- Minimum minutes threshold (configurable) removes unreliable small-sample players

### Tracking Data Integration (`analysis/tracking.py`)

**Coordinate systems**:
- StatsBomb: 120×80 yards, origin top-left
- Standard metres: Configurable pitch dimensions (default 105×68m)
- Conversion: Linear scaling with y-axis flip

**Pitch control model** (simplified Fernandez & Bornn 2018):
- Gaussian influence field per player based on position and velocity
- Influence radius: 5m default (configurable)
- Grid resolution: configurable (default 50×34)
- Output: 2D array where values in [-1, 1] represent team control

**Physical metrics**:
- Distance: Euclidean between consecutive frames
- Speed: Distance / time between frames
- Sprints: Consecutive frames above threshold (default 7 m/s)

**Team shape analysis**:
- Centroid: Mean position of outfield players
- Spread: Standard deviation of distances from centroid
- Compactness: Convex hull area of team positions

### Assumptions & Limitations

1. **Sample size**: Individual match analysis has high variance — use multi-match aggregates for reliable conclusions
2. **Context missing**: xG doesn't capture goalkeeper quality, defensive pressure quality, or player intent
3. **Selection bias**: StatsBomb open data covers selected competitions only — findings may not generalise
4. **Tracking data**: Supported via adapters (Metrica/EPTS formats) but not included in StatsBomb open data — requires separate data source
5. **Temporal resolution**: Events are timestamped to the second — sub-second interactions between events are estimated
6. **xG model scope**: Custom model trained on StatsBomb features only — does not include pre-shot movement, GK positioning, or defensive block data

### Statistical Methods

- **Rolling averages**: 5-match window for form analysis (trade-off: responsiveness vs noise)
- **Percentile ranks**: Non-parametric comparison across player populations
- **Kernel Density Estimation**: For heatmaps (bandwidth selected by Scott's rule)
- **Network centrality**: Could be added for passing network hub identification (not yet implemented)

## Evaluation Framework

### For Opponent Profiling
- **Validity**: Does the profile predict the opponent's actual approach in the next match?
- **Metric**: Compare predicted play patterns vs observed in subsequent match
- **Baseline**: Naive prediction = "same as season average"

### For Player Performance
- **Reliability**: Do metrics correlate match-to-match? (test-retest)
- **Validity**: Do high-xG players actually score more over a season?
- **Metric**: Correlation between player xG and actual goals (r > 0.85 typical)

## Report Templates

### Executive Summary Template (3-5 bullets)
```
1. [INSIGHT]: [Metric] shows [finding] — recommend [action]
2. [INSIGHT]: [Player/Team] [trend] over last [N] matches — [implication]
3. [RISK]: Opponent strong from [pattern] — prepare [counter-tactic]
4. [OPPORTUNITY]: Opponent weak in [zone/situation] — exploit via [method]
5. [TREND]: [Metric] has [improved/declined] by [X%] since [date] — [context]
```

### Technical Report Structure
1. Match/Analysis context (competition, teams, date)
2. Key metrics table
3. Visualisations with interpretive captions
4. Comparison to benchmarks (league average, previous meetings)
5. Limitations and confidence level
6. Actionable recommendations
