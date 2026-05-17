"""Opponent profiling module.

Produces pre-match scouting reports: attacking patterns, defensive shape,
set-piece tendencies, and key player threats.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.db import get_engine


def get_opponent_attack_patterns(
    engine: Engine,
    team_id: int,
    season_id: int,
) -> pd.DataFrame:
    """Summarise how an opponent builds attacks by play pattern.

    Metrics: possession count, shots generated, avg xG per shot, goals.
    Football insight: Identifies whether a team is dangerous from open play,
    set pieces, counters, etc. — critical for match preparation.
    """
    query = text("""
        SELECT
            e.play_pattern,
            COUNT(DISTINCT e.possession) AS possessions,
            COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots,
            ROUND((AVG(e.xg) FILTER (WHERE e.event_type = 'Shot'))::NUMERIC, 3) AS avg_xg,
            ROUND((SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'))::NUMERIC, 2) AS total_xg,
            COUNT(*) FILTER (WHERE e.shot_outcome = 'Goal') AS goals
        FROM events e
        JOIN matches m ON e.match_id = m.match_id
        WHERE e.team_id = :team_id
          AND m.season_id = :season_id
        GROUP BY e.play_pattern
        ORDER BY total_xg DESC NULLS LAST
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"team_id": team_id, "season_id": season_id})


def get_opponent_defensive_shape(
    engine: Engine,
    team_id: int,
    season_id: int,
) -> pd.DataFrame:
    """Analyse opponent's defensive actions by pitch zone.

    Splits pitch into thirds and counts tackles, interceptions, pressures.
    Football insight: High defensive line = vulnerable to through balls.
    """
    query = text("""
        SELECT
            CASE
                WHEN e.location_x < 40 THEN 'Defensive Third'
                WHEN e.location_x < 80 THEN 'Middle Third'
                ELSE 'Attacking Third'
            END AS zone,
            COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures,
            COUNT(*) FILTER (WHERE e.event_type = 'Tackle') AS tackles,
            COUNT(*) FILTER (WHERE e.event_type = 'Interception') AS interceptions,
            COUNT(*) FILTER (WHERE e.event_type = 'Block') AS blocks,
            ROUND((AVG(e.location_x) FILTER (WHERE e.event_type IN ('Tackle', 'Interception')))::NUMERIC, 1) AS avg_defensive_x
        FROM events e
        JOIN matches m ON e.match_id = m.match_id
        WHERE e.team_id = :team_id
          AND m.season_id = :season_id
          AND e.event_type IN ('Pressure', 'Tackle', 'Interception', 'Block')
        GROUP BY zone
        ORDER BY zone
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"team_id": team_id, "season_id": season_id})


def get_opponent_key_players(
    engine: Engine,
    team_id: int,
    season_id: int,
    top_n: int = 5,
) -> pd.DataFrame:
    """Identify opponent's most dangerous players by combined xG + xA.

    Football insight: Helps coaches assign marking responsibilities.
    """
    query = text("""
        SELECT
            p.player_name,
            COUNT(DISTINCT e.match_id) AS matches,
            SUM(e.xg) FILTER (WHERE e.event_type = 'Shot') AS total_xg,
            SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL) AS total_xa,
            COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0) +
                COALESCE(SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL), 0) AS xg_plus_xa,
            COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots,
            COUNT(*) FILTER (WHERE e.key_pass) AS key_passes,
            COUNT(*) FILTER (WHERE e.event_type = 'Dribble' AND e.dribble_outcome = 'Complete') AS dribbles
        FROM events e
        JOIN players p ON e.player_id = p.player_id
        JOIN matches m ON e.match_id = m.match_id
        WHERE e.team_id = :team_id
          AND m.season_id = :season_id
        GROUP BY p.player_name
        ORDER BY xg_plus_xa DESC NULLS LAST
        LIMIT :top_n
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"team_id": team_id, "season_id": season_id, "top_n": top_n})


def build_opponent_report(
    team_id: int,
    season_id: int,
    engine: Engine | None = None,
) -> dict[str, Any]:
    """Build a complete opponent scouting report.

    Returns a dict with DataFrames suitable for dashboard display.
    """
    if engine is None:
        engine = get_engine()

    return {
        "attack_patterns": get_opponent_attack_patterns(engine, team_id, season_id),
        "defensive_shape": get_opponent_defensive_shape(engine, team_id, season_id),
        "key_players": get_opponent_key_players(engine, team_id, season_id),
    }
