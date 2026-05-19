# REST API Guide

## Overview

MatchMind provides a **FastAPI** REST layer for external integrations. The API is fully documented with Pydantic validation, CORS support, and automatic OpenAPI documentation.

**Base URL**: `http://localhost:8080/api/v1` (or configured in `.env`)

**OpenAPI Docs**: `http://localhost:8080/docs`

**ReDoc**: `http://localhost:8080/redoc`

## Authentication & Security

⚠️ **No authentication required** for public endpoints (current version).

For production deployments:
- Implement API key authentication
- Use OAuth 2.0 with bearer tokens
- Restrict CORS origins via `CORS_ORIGINS` environment variable

## CORS Configuration

CORS is configured via environment variables:

```bash
# In .env
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
CORS_METHODS=GET,POST,OPTIONS
CORS_HEADERS=Content-Type,Authorization
```

Default (if not set):
- Origins: `localhost:*` (all localhost ports)
- Methods: `GET,POST`
- Credentials: Not allowed

## Endpoints

### 1. Health Check

**Endpoint**: `GET /api/v1/health`

**Description**: Verify API is running and database is accessible.

**Response**:
```json
{
  "status": "ok",
  "version": "0.3.0",
  "database": "connected",
  "timestamp": "2026-05-19T14:32:15Z"
}
```

**Example**:
```bash
curl http://localhost:8080/api/v1/health
```

---

### 2. Player Profile

**Endpoint**: `GET /api/v1/players/{id}/profile`

**Description**: Get season-level performance metrics for a player.

**Path Parameters**:
- `id` (int): Player ID (StatsBomb ID)

**Query Parameters**:
- `season_id` (int, optional): Season ID. If omitted, returns all seasons

**Response**:
```json
{
  "player_id": 5503,
  "player_name": "Lionel Messi",
  "team_id": 771,
  "team_name": "Argentina",
  "season_id": 106,
  "appearances": 22,
  "minutes_played": 1980,
  "xg_total": 8.3,
  "xa_total": 5.2,
  "xg_per_90": 0.378,
  "xa_per_90": 0.236,
  "goals": 7,
  "assists": 4,
  "passes": 1240,
  "pass_accuracy": 0.841,
  "tackles": 45,
  "interceptions": 34,
  "pressures": 156,
  "successful_pressures": 68,
  "dribbles": 98,
  "fouls": 12,
  "yellow_cards": 2
}
```

**Example**:
```bash
curl http://localhost:8080/api/v1/players/5503/profile?season_id=106
```

---

### 3. Similar Players

**Endpoint**: `GET /api/v1/players/{id}/similar`

**Description**: Find similar players using cosine similarity on per-90 statistics.

**Path Parameters**:
- `id` (int): Player ID to find matches for

**Query Parameters**:
- `season_id` (int): Season ID
- `top_n` (int, default=10): Number of similar players to return
- `position` (str, optional): Filter by position (e.g., "FW", "MF", "DF")

**Response**:
```json
[
  {
    "player_id": 6909,
    "player_name": "Ángel Di María",
    "team_id": 771,
    "team_name": "Argentina",
    "position": "Right Wing",
    "similarity": 0.947,
    "xg_per_90": 0.285,
    "xa_per_90": 0.198,
    "pass_accuracy": 0.823
  },
  {
    "player_id": 5206,
    "player_name": "Cristiano Ronaldo",
    "team_id": 695,
    "team_name": "Portugal",
    "position": "Right Wing",
    "similarity": 0.912,
    "xg_per_90": 0.342,
    "xa_per_90": 0.168,
    "pass_accuracy": 0.766
  }
]
```

**Example**:
```bash
curl "http://localhost:8080/api/v1/players/5503/similar?season_id=106&top_n=5"
```

---

### 4. Player Development

**Endpoint**: `GET /api/v1/players/{id}/development`

**Description**: Get multi-season development trajectory with trend analysis.

**Path Parameters**:
- `id` (int): Player ID

**Response**:
```json
{
  "player_id": 5503,
  "player_name": "Lionel Messi",
  "seasons": [
    {
      "season_id": 104,
      "season_name": "2020/21",
      "xg_per_90": 0.342,
      "xa_per_90": 0.195,
      "appearances": 19
    },
    {
      "season_id": 105,
      "season_name": "2021/22",
      "xg_per_90": 0.356,
      "xa_per_90": 0.208,
      "appearances": 21
    }
  ],
  "trajectory": "improving",
  "trend_slope": 0.0142,
  "peak_season": 105,
  "breakout_candidate": false
}
```

**Example**:
```bash
curl http://localhost:8080/api/v1/players/5503/development
```

---

### 5. Team Set-Pieces

**Endpoint**: `GET /api/v1/teams/{id}/set-pieces`

**Description**: Get set-piece efficiency metrics (corners, free kicks).

**Path Parameters**:
- `id` (int): Team ID

**Query Parameters**:
- `season_id` (int): Season ID

**Response**:
```json
{
  "team_id": 771,
  "team_name": "Argentina",
  "season_id": 106,
  "set_piece_efficiency": {
    "corner_total": 28,
    "corner_goals": 2,
    "corner_xg_generated": 4.5,
    "corner_success_rate": 0.071,
    "free_kick_total": 45,
    "free_kick_goals": 1,
    "free_kick_xg_generated": 2.3,
    "free_kick_success_rate": 0.022,
    "throw_in_total": 120,
    "throw_in_goals": 0
  },
  "dangerous_zones": [
    {
      "zone": "near_post",
      "frequency": 12,
      "goals": 1,
      "xg": 2.1
    }
  ]
}
```

**Example**:
```bash
curl "http://localhost:8080/api/v1/teams/771/set-pieces?season_id=106"
```

---

### 6. Team Possession Profile

**Endpoint**: `GET /api/v1/teams/{id}/possession-profile`

**Description**: Get possession chain analysis (build-up patterns, transitions).

**Path Parameters**:
- `id` (int): Team ID

**Query Parameters**:
- `season_id` (int): Season ID

**Response**:
```json
{
  "team_id": 771,
  "team_name": "Argentina",
  "season_id": 106,
  "possession_profile": {
    "total_chains": 2145,
    "avg_chain_duration": 18.3,
    "avg_passes_per_chain": 6.2,
    "dangerous_possession_rate": 0.238,
    "box_entry_rate": 0.156,
    "xg_per_chain": 0.084,
    "total_xg_from_chains": 180.4,
    "style_distribution": {
      "short_passing": 0.45,
      "wing_play": 0.28,
      "counter_attack": 0.18,
      "direct": 0.09
    }
  },
  "transition_metrics": {
    "offensive_transitions": {
      "count": 287,
      "success_rate": 0.42,
      "avg_players_involved": 3.1
    },
    "defensive_transitions": {
      "count": 312,
      "success_rate": 0.68,
      "recovery_time_seconds": 4.2
    }
  }
}
```

**Example**:
```bash
curl "http://localhost:8080/api/v1/teams/771/possession-profile?season_id=106"
```

---

### 7. xG Prediction

**Endpoint**: `POST /api/v1/xg/predict`

**Description**: Predict expected goals (xG) for shot(s).

**Request Body**:
```json
{
  "distance_to_goal": 12.5,
  "goal_angle": 45.0,
  "is_header": false,
  "under_pressure": false,
  "is_penalty": false,
  "body_part": "right_foot"
}
```

**Response**:
```json
{
  "xg": 0.187,
  "model": "logistic_regression",
  "calibration": {
    "brier_score": 0.071,
    "roc_auc": 0.782,
    "log_loss": 0.238
  }
}
```

**Batch prediction**:
```json
POST /api/v1/xg/predict
[
  {
    "distance_to_goal": 12.5,
    "goal_angle": 45.0,
    "is_header": false,
    "under_pressure": false
  },
  {
    "distance_to_goal": 18.0,
    "goal_angle": 32.0,
    "is_header": true,
    "under_pressure": true
  }
]
```

**Example**:
```bash
curl -X POST http://localhost:8080/api/v1/xg/predict \
  -H "Content-Type: application/json" \
  -d '{
    "distance_to_goal": 12.5,
    "goal_angle": 45.0,
    "is_header": false,
    "under_pressure": false
  }'
```

---

### 8. Match Simulation

**Endpoint**: `POST /api/v1/simulation/match`

**Description**: Simulate match outcome using Monte Carlo (Poisson-based).

**Request Body**:
```json
{
  "home_xg": 1.8,
  "away_xg": 1.2,
  "home_team": "Arsenal",
  "away_team": "Chelsea",
  "iterations": 10000
}
```

**Response**:
```json
{
  "home_win": 0.482,
  "draw": 0.241,
  "away_win": 0.277,
  "most_likely_score": "2-1",
  "score_probabilities": [
    {"score": "0-0", "probability": 0.032},
    {"score": "1-0", "probability": 0.145},
    {"score": "1-1", "probability": 0.121},
    {"score": "2-0", "probability": 0.089},
    {"score": "2-1", "probability": 0.108}
  ],
  "btts": 0.521,
  "over_2_5": 0.543,
  "home_team": "Arsenal",
  "away_team": "Chelsea"
}
```

**Example**:
```bash
curl -X POST http://localhost:8080/api/v1/simulation/match \
  -H "Content-Type: application/json" \
  -d '{
    "home_xg": 1.8,
    "away_xg": 1.2,
    "iterations": 5000
  }'
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Data returned correctly |
| 400 | Bad Request | Invalid parameters or missing required fields |
| 404 | Not Found | Player/team/season doesn't exist |
| 422 | Validation Error | Pydantic validation failed |
| 500 | Server Error | Database unavailable, unhandled exception |

### Error Response Format

```json
{
  "detail": "Team ID 99999 not found in season 106",
  "type": "value_error"
}
```

### Common Errors

**Invalid season_id**:
```bash
curl "http://localhost:8080/api/v1/players/5503/profile?season_id=999"
# Response: 404 Not Found
```

**Missing required field in POST**:
```bash
curl -X POST http://localhost:8080/api/v1/xg/predict -d '{}'
# Response: 422 Validation Error - "field required"
```

---

## Authentication (Future)

When authentication is implemented:

```bash
# Add bearer token to header
curl -H "Authorization: Bearer your_api_key" \
  http://localhost:8080/api/v1/health
```

---

## Rate Limiting (Future)

Expected rate limits (when implemented):
- **Free tier**: 100 requests/minute
- **Pro tier**: 1000 requests/minute
- **Enterprise**: Custom limits

---

## Integration Examples

### Python (requests)
```python
import requests

# Get player profile
response = requests.get(
    "http://localhost:8080/api/v1/players/5503/profile",
    params={"season_id": 106}
)
data = response.json()
print(f"{data['player_name']}: {data['xg_per_90']:.3f} xG/90")
```

### JavaScript (fetch)
```javascript
// Find similar players
const response = await fetch(
  'http://localhost:8080/api/v1/players/5503/similar?season_id=106&top_n=5'
);
const similar = await response.json();
similar.forEach(p => {
  console.log(`${p.player_name}: ${p.similarity.toFixed(3)} similarity`);
});
```

### cURL with saved response
```bash
# Get and save match simulation result
curl -X POST http://localhost:8080/api/v1/simulation/match \
  -H "Content-Type: application/json" \
  -d '{"home_xg": 1.8, "away_xg": 1.2}' \
  | jq '.' > simulation_result.json
```

---

## Deployment

### Docker
```bash
docker run -p 8080:8080 \
  -e CORS_ORIGINS="http://localhost:3000" \
  matchmind:latest
```

### Manual start
```bash
uv run fb-api
```

### Production (with Gunicorn)
```bash
uv run gunicorn -w 4 -b 0.0.0.0:8080 \
  football_analytics.api:app \
  --worker-class uvicorn.workers.UvicornWorker
```

---

## Monitoring

### Health endpoint for monitoring
```bash
# Check API health every 30 seconds (suitable for uptime monitoring)
watch -n 30 'curl -s http://localhost:8080/api/v1/health | jq ".status"'
```

### Logging
API logs are written to standard output (stdout) and can be captured by:
- Docker container logs
- systemd journal
- Application monitoring tools (DataDog, New Relic, etc.)

---

## Future Enhancements

- [ ] WebSocket support for live updates
- [ ] GraphQL endpoint alongside REST
- [ ] Event streaming via Server-Sent Events (SSE)
- [ ] Batch operation optimization
- [ ] API versioning (v2, v3, etc.)
- [ ] OAuth 2.0 authentication
- [ ] Request/response caching headers
- [ ] OpenAPI schema download endpoint

---

## Support

For issues or feature requests:
- **Documentation**: See [README.md](../README.md)
- **Issues**: GitHub Issues
- **Email**: [support email]

---

## API Changelog

### v0.3.0 (May 2026)
- ✅ All endpoints implemented
- ✅ Pydantic validation
- ✅ CORS support
- ✅ OpenAPI documentation

### v0.2.0
- Initial REST API structure

### v0.1.0
- No API endpoint (ingestion pipeline only)
