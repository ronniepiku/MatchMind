"""Dashboard endpoints — data serving for the React frontend."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from football_analytics import response_cache

router = APIRouter(prefix="/api/v1", tags=["dashboard"])
logger = logging.getLogger(__name__)
_limiter = Limiter(key_func=get_remote_address)


# ─── Request Models ─────────────────────────────────────────────────────────


class SimulationV2Request(BaseModel):
    """Request model for v2 match simulation."""

    home_team_id: int = Field(..., gt=0, description="Home team ID")
    away_team_id: int = Field(..., gt=0, description="Away team ID")
    season_id: int = Field(..., gt=0, description="Season ID")


# ─── Reference Data ─────────────────────────────────────────────────────────


@router.get("/teams")
async def list_teams() -> list[dict[str, Any]]:
    """List all available teams."""
    cache_k = response_cache.cache_key("teams")
    cached = response_cache.get(cache_k)
    if cached is not None:
        return cached

    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text("SELECT DISTINCT team_id AS id, team_name AS name FROM teams ORDER BY team_name"),
            conn,
        )
    result = df.to_dict(orient="records")
    response_cache.put(cache_k, result, ttl_seconds=3600)
    return result


@router.get("/seasons")
async def list_seasons() -> list[dict[str, Any]]:
    """List all available seasons."""
    cache_k = response_cache.cache_key("seasons")
    cached = response_cache.get(cache_k)
    if cached is not None:
        return cached

    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text(
                "SELECT season_id AS id, season_name AS name, "
                "competition_name FROM competitions ORDER BY competition_name, season_name"
            ),
            conn,
        )
    result = df.to_dict(orient="records")
    response_cache.put(cache_k, result, ttl_seconds=3600)
    return result


@router.get("/players")
async def list_players(
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> list[dict[str, Any]]:
    """List players for a team/season combination."""
    cache_k = response_cache.cache_key("players", team_id=team_id, season_id=season_id)
    cached = response_cache.get(cache_k)
    if cached is not None:
        return cached

    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT DISTINCT p.player_id AS id, p.player_name AS name,
                       COALESCE(l.position, 'Unknown') AS position
                FROM players p
                JOIN events e ON p.player_id = e.player_id
                JOIN matches m ON e.match_id = m.match_id
                LEFT JOIN lineups l ON p.player_id = l.player_id
                    AND l.match_id = e.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                ORDER BY p.player_name
            """),
            conn,
            params={"team_id": team_id, "season_id": season_id},
        )
    result = df.to_dict(orient="records")
    response_cache.put(cache_k, result, ttl_seconds=1800)
    return result


@router.get("/matches")
async def list_matches(
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> list[dict[str, Any]]:
    """List matches for a team/season combination."""
    cache_k = response_cache.cache_key("matches", team_id=team_id, season_id=season_id)
    cached = response_cache.get(cache_k)
    if cached is not None:
        return cached

    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT m.match_id AS id,
                       ht.team_name AS home_team,
                       at.team_name AS away_team,
                       m.home_score,
                       m.away_score,
                       m.match_date AS date,
                       c.competition_name AS competition
                FROM matches m
                JOIN teams ht ON m.home_team_id = ht.team_id
                JOIN teams at ON m.away_team_id = at.team_id
                JOIN competitions c ON m.competition_id = c.competition_id
                WHERE (m.home_team_id = :team_id OR m.away_team_id = :team_id)
                  AND m.season_id = :season_id
                ORDER BY m.match_date DESC
            """),
            conn,
            params={"team_id": team_id, "season_id": season_id},
        )
    result = df.to_dict(orient="records")
    response_cache.put(cache_k, result, ttl_seconds=1800)
    return result


@router.get("/data-availability")
async def check_data_availability(
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> dict[str, Any]:
    """Check data availability for a team/season."""
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT COUNT(*) AS matches
                FROM matches
                WHERE (home_team_id = :team_id OR away_team_id = :team_id)
                  AND season_id = :season_id
            """),
            {"team_id": team_id, "season_id": season_id},
        ).fetchone()

    count = result[0] if result else 0
    return {"matches": count, "has_data": count > 0}


# ─── Opponent Profile ───────────────────────────────────────────────────────


@router.get("/opponent/report")
@_limiter.limit("15/minute")
async def get_opponent_report(
    request: Request,
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> dict[str, Any]:
    """Generate opponent scouting report."""
    cache_k = response_cache.cache_key("opponent_report", team_id=team_id, season_id=season_id)
    cached = response_cache.get(cache_k)
    if cached is not None:
        return cached

    from sqlalchemy import text as _text

    from football_analytics.analysis.opponent_profile import build_opponent_report
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    report = build_opponent_report(team_id, season_id, engine)

    if report is None:
        raise HTTPException(status_code=404, detail="No data for opponent report")

    with engine.connect() as conn:
        team_row = conn.execute(
            _text("SELECT team_name FROM teams WHERE team_id = :tid"),
            {"tid": team_id},
        ).fetchone()
    team_name = team_row[0] if team_row else "Unknown"

    attack_patterns = []
    ap_df = report.get("attack_patterns")
    if ap_df is not None and hasattr(ap_df, "empty") and not ap_df.empty:
        for _, row in ap_df.iterrows():
            possessions = int(row.get("possessions", 0))
            shots = int(row.get("shots", 0))
            success_rate = shots / max(possessions, 1)
            attack_patterns.append(
                {
                    "pattern_type": row.get("play_pattern", "Unknown"),
                    "frequency": possessions,
                    "success_rate": round(success_rate, 3),
                    "xg_per_attack": round(float(row.get("avg_xg", 0) or 0), 3),
                }
            )

    defensive_shape = []
    ds_df = report.get("defensive_shape")
    if ds_df is not None and hasattr(ds_df, "empty") and not ds_df.empty:
        for _, row in ds_df.iterrows():
            defensive_shape.append(
                {
                    "zone": row.get("zone", "Unknown"),
                    "tackles": int(row.get("tackles", 0)),
                    "interceptions": int(row.get("interceptions", 0)),
                    "pressures": int(row.get("pressures", 0)),
                    "recoveries": int(row.get("blocks", 0)),
                }
            )

    key_players = []
    kp_df = report.get("key_players")
    if kp_df is not None and hasattr(kp_df, "empty") and not kp_df.empty:
        for _, row in kp_df.iterrows():
            xg = float(row.get("total_xg", 0) or 0)
            xa = float(row.get("total_xa", 0) or 0)
            matches = int(row.get("matches", 1))
            threat = round((xg + xa) / max(matches, 1) * 10, 1)
            key_players.append(
                {
                    "player_name": row.get("player_name", "Unknown"),
                    "position": "FW",
                    "goals": int(row.get("shots", 0)),
                    "assists": int(row.get("key_passes", 0)),
                    "xg": round(xg, 2),
                    "xa": round(xa, 2),
                    "minutes": matches * 90,
                    "threat_rating": min(threat, 10.0),
                }
            )

    result = {
        "team_name": team_name,
        "attack_patterns": attack_patterns,
        "defensive_shape": defensive_shape,
        "key_players": key_players,
    }
    response_cache.put(cache_k, result, ttl_seconds=600)
    return result


# ─── Player Performance ────────────────────────────────────────────────────


@router.get("/player/summary")
async def get_player_summary(
    player_id: int = Query(...),
    season_id: int = Query(...),
) -> dict[str, Any]:
    """Get player season summary statistics."""
    cache_k = response_cache.cache_key("player_summary", player_id=player_id, season_id=season_id)
    cached = response_cache.get(cache_k)
    if cached is not None:
        return cached

    from football_analytics.analysis.player_performance import get_player_season_summary
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    summary_df = get_player_season_summary(engine, player_id, season_id)

    if summary_df is None or (hasattr(summary_df, "empty") and summary_df.empty):
        raise HTTPException(status_code=404, detail="Player data not found")

    row = summary_df.iloc[0]
    appearances = int(row.get("appearances", 0))
    total_xg = float(row.get("total_xg", 0) or 0)
    total_xa = float(row.get("total_xa", 0) or 0)
    minutes = appearances * 90

    result = {
        "matches_played": appearances,
        "minutes": minutes,
        "goals": int(row.get("goals", 0)),
        "assists": int(row.get("assists", 0)),
        "xg": round(total_xg, 2),
        "xa": round(total_xa, 2),
        "xg_per_90": round(total_xg / max(appearances, 1), 2),
        "xa_per_90": round(total_xa / max(appearances, 1), 2),
        "passes_completed": int(row.get("passes_completed", 0)),
        "pass_accuracy": round(float(row.get("pass_accuracy", 0) or 0) * 100, 1),
        "tackles_won": int(row.get("tackles", 0)),
        "interceptions": int(row.get("interceptions", 0)),
        "pressures": int(row.get("pressures", 0)),
    }
    response_cache.put(cache_k, result, ttl_seconds=600)
    return result


@router.get("/player/rolling-form")
async def get_player_rolling_form(
    player_id: int = Query(...),
    season_id: int = Query(...),
) -> list[dict[str, Any]]:
    """Get player rolling form data."""
    from football_analytics.analysis.player_performance import get_player_rolling_form
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    form_data = get_player_rolling_form(engine, player_id, season_id)

    if form_data is None or (hasattr(form_data, "empty") and form_data.empty):
        return []

    results = []
    for _, row in form_data.iterrows():
        match_date = str(row.get("match_date", ""))
        results.append(
            {
                "match_date": match_date,
                "match_label": match_date[:10] if match_date else "",
                "xg": round(float(row.get("match_xg", 0) or 0), 3),
                "xa": round(float(row.get("match_xa", 0) or 0), 3),
                "xg_rolling": round(float(row.get("rolling_xg", 0) or 0), 3),
                "xa_rolling": round(float(row.get("rolling_xa", 0) or 0), 3),
            }
        )
    return results


@router.get("/player/radar")
async def get_player_radar(
    player_id: int = Query(...),
    season_id: int = Query(...),
) -> list[dict[str, Any]]:
    """Get player radar percentile data."""
    from football_analytics.analysis.player_performance import get_player_radar_percentiles
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    radar_data = get_player_radar_percentiles(engine, player_id, season_id)

    if radar_data is None or (hasattr(radar_data, "empty") and radar_data.empty):
        return []

    row = radar_data.iloc[0]
    metric_labels = {
        "xg_per_match": "xG per Match",
        "xa_per_match": "xA per Match",
        "passes_per_match": "Passes",
        "dribbles_per_match": "Dribbles",
        "pressures_per_match": "Pressures",
        "def_actions_per_match": "Defensive Actions",
    }
    results = []
    for col, label in metric_labels.items():
        if col in row.index:
            pct = float(row[col])
            results.append({"metric": label, "value": round(pct, 1), "percentile": round(pct, 1)})
    return results


@router.get("/player/squad-comparison")
async def get_squad_comparison(
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> list[dict[str, Any]]:
    """Get squad comparison data."""
    from football_analytics.analysis.player_performance import get_squad_comparison
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    comparison = get_squad_comparison(engine, team_id, season_id)

    if comparison is None or (hasattr(comparison, "empty") and comparison.empty):
        return []

    results = []
    for _, row in comparison.iterrows():
        appearances = int(row.get("appearances", 1))
        total_xg = float(row.get("total_xg", 0) or 0)
        total_xa = float(row.get("total_xa", 0) or 0)
        goals = int(row.get("goals", 0))
        assists = int(row.get("assists", 0))
        xg_per_90 = total_xg / max(appearances, 1)
        xa_per_90 = total_xa / max(appearances, 1)
        rating = min(10.0, round((xg_per_90 + xa_per_90) * 5 + 4, 1))
        results.append(
            {
                "player_name": row.get("player_name", "Unknown"),
                "position": "MF",
                "minutes": appearances * 90,
                "goals": goals,
                "assists": assists,
                "xg_per_90": round(xg_per_90, 2),
                "xa_per_90": round(xa_per_90, 2),
                "rating": rating,
            }
        )
    return results


# ─── Team Scorecard ─────────────────────────────────────────────────────────


@router.get("/team/scorecard")
@_limiter.limit("10/minute")
async def get_team_scorecard(
    request: Request,
    team_id: int = Query(...),
    season_id: int = Query(...),
) -> dict[str, Any]:
    """Generate comprehensive team scorecard."""
    cache_k = response_cache.cache_key("team_scorecard", team_id=team_id, season_id=season_id)
    cached = response_cache.get(cache_k)
    if cached is not None:
        return cached

    import pandas as pd
    from sqlalchemy import text

    from football_analytics.analysis.opponent_profile import get_opponent_defensive_shape
    from football_analytics.analysis.possession_chains import (
        chains_to_dataframe,
        compute_team_possession_profile,
        compute_transition_metrics,
        extract_possession_chains,
    )
    from football_analytics.analysis.set_pieces import (
        compute_set_piece_efficiency,
        extract_set_pieces,
        set_pieces_to_dataframe,
    )
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()

    with engine.connect() as conn:
        events_df = pd.read_sql(
            text("""
                SELECT e.match_id, e.team_id, e.player_id, e.event_type,
                       e.minute, e.second, e.location_x, e.location_y,
                       e.end_location_x, e.end_location_y,
                       e.pass_outcome, e.pass_length, e.play_pattern,
                       e.xg, e.shot_outcome, e.possession,
                       e.under_pressure, e.key_pass
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE (m.home_team_id = :team_id OR m.away_team_id = :team_id)
                  AND m.season_id = :season_id
                ORDER BY e.match_id, e.minute, e.second
            """),
            conn,
            params={"team_id": team_id, "season_id": season_id},
        )

    if events_df.empty:
        raise HTTPException(status_code=404, detail="No event data found")

    chains = extract_possession_chains(events_df)
    chains_df = chains_to_dataframe(chains)
    profile = compute_team_possession_profile(chains_df, team_id)
    transitions = compute_transition_metrics(chains)

    sp_events = events_df[events_df["play_pattern"].isin(["From Corner", "From Free Kick", "From Throw In"])]
    sp_sequences = extract_set_pieces(sp_events) if not sp_events.empty else []
    sp_df = set_pieces_to_dataframe(sp_sequences) if sp_sequences else pd.DataFrame()
    sp_efficiency = compute_set_piece_efficiency(sp_df, team_id) if not sp_df.empty else {}

    defensive_shape = get_opponent_defensive_shape(engine, team_id, season_id)

    team_events = events_df[events_df["team_id"] == team_id]
    n_matches = events_df["match_id"].nunique()
    shots = team_events[team_events["event_type"] == "Shot"]
    total_xg = float(shots["xg"].sum()) if "xg" in shots.columns else 0.0

    kpis = [
        {"label": "Matches", "value": n_matches, "unit": ""},
        {"label": "Total xG", "value": round(total_xg, 2), "unit": ""},
        {"label": "xG/Match", "value": round(total_xg / max(n_matches, 1), 2), "unit": ""},
        {"label": "Possession Chains", "value": profile.get("total_chains", 0), "unit": ""},
        {
            "label": "Dangerous Poss %",
            "value": round(profile.get("dangerous_possession_rate", 0) * 100, 1),
            "unit": "%",
        },
    ]

    possession_profile = [
        {"style": k, "percentage": round(v * 100, 1)} for k, v in profile.get("style_distribution", {}).items()
    ]

    pressing_data = []
    if defensive_shape is not None and hasattr(defensive_shape, "iterrows") and not defensive_shape.empty:
        for _, zone_data in defensive_shape.iterrows():
            pressing_data.append(
                {
                    "zone": zone_data.get("zone", "Unknown"),
                    "pressures_per_90": round(int(zone_data.get("pressures", 0)) / max(n_matches, 1) * (90 / 95), 1),
                }
            )
    elif isinstance(defensive_shape, list):
        for zone_data in defensive_shape:
            if isinstance(zone_data, dict):
                pressing_data.append(
                    {
                        "zone": zone_data.get("zone", "Unknown"),
                        "pressures_per_90": round(zone_data.get("pressures", 0) / max(n_matches, 1) * (90 / 95), 1),
                    }
                )

    transition_metrics = []
    if transitions and isinstance(transitions, dict):
        for metric_name, value in transitions.items():
            transition_metrics.append(
                {
                    "metric": metric_name.replace("_", " ").title(),
                    "value": round(value, 2) if isinstance(value, (int, float)) else 0,
                    "league_avg": 0,
                    "percentile": 50,
                }
            )

    set_pieces_list = []
    if sp_efficiency and isinstance(sp_efficiency, dict):
        for sp_type in ["corner", "free_kick", "throw_in"]:
            count = sp_efficiency.get(f"{sp_type}_count", 0)
            if count:
                set_pieces_list.append(
                    {
                        "type": sp_type.replace("_", " ").title(),
                        "total": count,
                        "chances_created": sp_efficiency.get(f"{sp_type}_chances", 0),
                        "goals": sp_efficiency.get(f"{sp_type}_goals", 0),
                        "xg": round(sp_efficiency.get(f"{sp_type}_xg", 0), 2),
                        "conversion_rate": round(sp_efficiency.get(f"{sp_type}_goal_rate", 0), 3),
                    }
                )

    result = {
        "kpis": kpis,
        "possession_profile": possession_profile,
        "pressing_intensity": pressing_data,
        "transitions": transition_metrics,
        "set_pieces": set_pieces_list,
    }
    response_cache.put(cache_k, result, ttl_seconds=900)
    return result


# ─── Match Analysis ────────────────────────────────────────────────────────


@router.get("/match/shots")
async def get_match_shots(match_id: int = Query(...)) -> list[dict[str, Any]]:
    """Get shot events for a match."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT e.location_x AS x, e.location_y AS y,
                       COALESCE(e.xg, 0) AS xg,
                       LOWER(COALESCE(e.shot_outcome, 'off_target')) AS outcome,
                       p.player_name, e.minute,
                       t.team_name AS team,
                       COALESCE(e.shot_body_part, 'Foot') AS body_part,
                       COALESCE(e.shot_technique, 'Normal') AS technique
                FROM events e
                LEFT JOIN players p ON e.player_id = p.player_id
                LEFT JOIN teams t ON e.team_id = t.team_id
                WHERE e.match_id = :match_id AND e.event_type = 'Shot'
                ORDER BY e.minute
            """),
            conn,
            params={"match_id": match_id},
        )
    outcome_map = {
        "goal": "goal",
        "saved": "saved",
        "blocked": "blocked",
        "off target": "off_target",
        "off_target": "off_target",
        "post": "post",
        "wayward": "off_target",
    }
    df["outcome"] = df["outcome"].map(lambda x: outcome_map.get(x, "off_target"))
    return df.to_dict(orient="records")


@router.get("/match/xg-timeline")
async def get_xg_timeline(match_id: int = Query(...)) -> list[dict[str, Any]]:
    """Get xG timeline events for a match."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT e.minute, t.team_name AS team,
                       COALESCE(e.xg, 0) AS xg, p.player_name,
                       LOWER(COALESCE(e.shot_outcome, 'off_target')) AS outcome
                FROM events e
                LEFT JOIN players p ON e.player_id = p.player_id
                LEFT JOIN teams t ON e.team_id = t.team_id
                WHERE e.match_id = :match_id AND e.event_type = 'Shot'
                ORDER BY e.minute
            """),
            conn,
            params={"match_id": match_id},
        )

    records = []
    team_cum: dict[str, float] = {}
    for _, row in df.iterrows():
        team = row["team"]
        team_cum[team] = team_cum.get(team, 0) + row["xg"]
        records.append(
            {
                "minute": int(row["minute"]),
                "team": team,
                "xg": round(float(row["xg"]), 3),
                "cumulative_xg": round(team_cum[team], 3),
                "player_name": row["player_name"],
                "outcome": row["outcome"],
            }
        )
    return records


@router.get("/match/passing-network")
async def get_passing_network(
    match_id: int = Query(...),
    team_id: int = Query(...),
) -> dict[str, Any]:
    """Get passing network data for a team in a match."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        passes_df = pd.read_sql(
            text("""
                SELECT e.player_id, p.player_name,
                       COALESCE(p.position, 'Unknown') AS position,
                       e.location_x, e.location_y, e.pass_recipient_id
                FROM events e
                LEFT JOIN players p ON e.player_id = p.player_id
                WHERE e.match_id = :match_id AND e.team_id = :team_id
                  AND e.event_type = 'Pass' AND e.pass_outcome IS NULL
                  AND e.minute <= 70
                ORDER BY e.minute
            """),
            conn,
            params={"match_id": match_id, "team_id": team_id},
        )

    if passes_df.empty:
        return {"nodes": [], "edges": []}

    avg_pos = (
        passes_df.groupby(["player_id", "player_name", "position"])
        .agg(x=("location_x", "mean"), y=("location_y", "mean"), passes_made=("player_id", "count"))
        .reset_index()
    )
    avg_pos = avg_pos.nlargest(11, "passes_made")

    nodes = [
        {
            "player_name": row["player_name"],
            "position": row["position"],
            "x": round(float(row["x"]), 1),
            "y": round(float(row["y"]), 1),
            "passes_made": int(row["passes_made"]),
        }
        for _, row in avg_pos.iterrows()
    ]

    active_ids = set(avg_pos["player_id"].values)
    edge_df = passes_df[passes_df["player_id"].isin(active_ids) & passes_df["pass_recipient_id"].isin(active_ids)]
    id_to_name = dict(zip(avg_pos["player_id"], avg_pos["player_name"], strict=False))
    edge_counts = edge_df.groupby(["player_id", "pass_recipient_id"]).size().reset_index(name="passes")
    edge_counts = edge_counts[edge_counts["passes"] >= 3]

    edges = [
        {
            "source": id_to_name.get(row["player_id"], "Unknown"),
            "target": id_to_name.get(row["pass_recipient_id"], "Unknown"),
            "passes": int(row["passes"]),
            "progressive": 0,
        }
        for _, row in edge_counts.iterrows()
    ]

    return {"nodes": nodes, "edges": edges}


@router.get("/match/pressure-map")
async def get_pressure_map(
    match_id: int = Query(...),
    team_id: int = Query(...),
) -> list[dict[str, Any]]:
    """Get pressure events for a team in a match."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT e.location_x AS x, e.location_y AS y,
                       e.counterpress AS success, e.minute, p.player_name
                FROM events e
                LEFT JOIN players p ON e.player_id = p.player_id
                WHERE e.match_id = :match_id AND e.team_id = :team_id
                  AND e.event_type = 'Pressure'
                ORDER BY e.minute
            """),
            conn,
            params={"match_id": match_id, "team_id": team_id},
        )
    return df.to_dict(orient="records")


# ─── Player Similarity (v2) ────────────────────────────────────────────────


@router.get("/player/similar")
async def get_similar_players_v2(
    player_id: int = Query(...),
    season_id: int = Query(106),
    top_n: int = Query(10, ge=1, le=50),
) -> list[dict[str, Any]]:
    """Find similar players (for frontend)."""
    from football_analytics.analysis.similarity import (
        compute_player_vectors,
        find_similar_players,
    )
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()
    try:
        vectors = compute_player_vectors(season_id, engine=engine, min_appearances=3)
    except Exception:
        logger.exception("Similarity computation failed")
        raise HTTPException(status_code=500, detail="Internal server error")

    if player_id not in vectors["player_id"].values:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    similar = find_similar_players(player_id, vectors, top_n=top_n)

    return [
        {
            "player_name": row["player_name"],
            "team": row.get("team_name", "Unknown"),
            "position": row.get("position", "Unknown"),
            "similarity_score": round(float(row["similarity"]), 3),
            "age": int(row.get("age", 0)),
            "minutes": int(row.get("minutes", 0)),
            "key_metrics": {},
        }
        for _, row in similar.iterrows()
    ]


# ─── Match Simulation (v2) ─────────────────────────────────────────────────


@router.post("/simulation/match")
async def simulate_match_v2(request: Request, sim_req: SimulationV2Request) -> dict[str, Any]:
    """Run match simulation using team IDs and historical xG data."""
    import pandas as pd
    from sqlalchemy import text

    from football_analytics.analysis.simulation import simulate_match
    from football_analytics.db import get_engine as _get_engine

    engine = _get_engine()

    with engine.connect() as conn:
        home_xg_df = pd.read_sql(
            text("""
                SELECT COALESCE(AVG(match_xg), 1.3) AS avg_xg FROM (
                    SELECT SUM(COALESCE(e.xg, 0)) AS match_xg
                    FROM events e
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE e.team_id = :team_id AND m.season_id = :season_id AND e.event_type = 'Shot'
                    GROUP BY e.match_id
                ) sub
            """),
            conn,
            params={"team_id": sim_req.home_team_id, "season_id": sim_req.season_id},
        )
        away_xg_df = pd.read_sql(
            text("""
                SELECT COALESCE(AVG(match_xg), 1.1) AS avg_xg FROM (
                    SELECT SUM(COALESCE(e.xg, 0)) AS match_xg
                    FROM events e
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE e.team_id = :team_id AND m.season_id = :season_id AND e.event_type = 'Shot'
                    GROUP BY e.match_id
                ) sub
            """),
            conn,
            params={"team_id": sim_req.away_team_id, "season_id": sim_req.season_id},
        )
        teams_df = pd.read_sql(
            text("SELECT team_id, team_name FROM teams WHERE team_id IN (:h, :a)"),
            conn,
            params={"h": sim_req.home_team_id, "a": sim_req.away_team_id},
        )

    home_xg = float(home_xg_df["avg_xg"].iloc[0]) if not home_xg_df.empty else 1.3
    away_xg = float(away_xg_df["avg_xg"].iloc[0]) if not away_xg_df.empty else 1.1

    home_name, away_name = "Home", "Away"
    for _, row in teams_df.iterrows():
        if row["team_id"] == sim_req.home_team_id:
            home_name = row["team_name"]
        elif row["team_id"] == sim_req.away_team_id:
            away_name = row["team_name"]

    result = simulate_match(
        home_xg=home_xg, away_xg=away_xg, home_team=home_name, away_team=away_name, n_simulations=10000
    )

    top_scores = sorted(result.scoreline_probabilities.items(), key=lambda x: x[1], reverse=True)[:15]
    scoreline_dist = [{"score": f"{h}-{a}", "probability": round(prob, 4)} for (h, a), prob in top_scores]

    return {
        "home_win_prob": round(result.home_win_prob, 4),
        "draw_prob": round(result.draw_prob, 4),
        "away_win_prob": round(result.away_win_prob, 4),
        "expected_home_goals": round(result.expected_home_goals, 2),
        "expected_away_goals": round(result.expected_away_goals, 2),
        "most_likely_score": f"{result.most_likely_score[0]}-{result.most_likely_score[1]}",
        "over_2_5_prob": round(result.over_2_5_prob, 4),
        "btts_prob": round(result.btts_prob, 4),
        "scoreline_distribution": scoreline_dist,
    }
