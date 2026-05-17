"""Player performance analysis module.

Computes per-player metrics, rolling form, radar profiles,
and comparative rankings within a squad or across the league.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


def get_player_season_summary(
    engine: Engine,
    player_id: int,
    season_id: int,
) -> pd.DataFrame:
    """Comprehensive season summary for a single player.

    Metrics: goals, xG, xA, passes, progressive carries, pressures, etc.
    Football insight: One-page performance overview for recruitment or review.
    """
    query = text("""
        SELECT
            p.player_name,
            t.team_name,
            COUNT(DISTINCT e.match_id) AS appearances,
            COUNT(*) FILTER (WHERE e.event_type = 'Shot' AND e.shot_outcome = 'Goal') AS goals,
            ROUND(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot')::NUMERIC, 2) AS total_xg,
            COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots,
            ROUND(SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL)::NUMERIC, 2) AS total_xa,
            COUNT(*) FILTER (WHERE e.key_pass) AS key_passes,
            COUNT(*) FILTER (WHERE e.assist) AS assists,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS passes_completed,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass') AS passes_attempted,
            ROUND(
                COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL)::NUMERIC /
                NULLIF(COUNT(*) FILTER (WHERE e.event_type = 'Pass'), 0), 3
            ) AS pass_accuracy,
            COUNT(*) FILTER (WHERE e.event_type = 'Dribble' AND e.dribble_outcome = 'Complete') AS successful_dribbles,
            COUNT(*) FILTER (WHERE e.event_type = 'Dribble') AS dribbles_attempted,
            COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures,
            COUNT(*) FILTER (WHERE e.event_type = 'Tackle') AS tackles,
            COUNT(*) FILTER (WHERE e.event_type = 'Interception') AS interceptions
        FROM events e
        JOIN players p ON e.player_id = p.player_id
        JOIN teams t ON e.team_id = t.team_id
        JOIN matches m ON e.match_id = m.match_id
        WHERE e.player_id = :player_id
          AND m.season_id = :season_id
        GROUP BY p.player_name, t.team_name
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"player_id": player_id, "season_id": season_id})


def get_player_rolling_form(
    engine: Engine,
    player_id: int,
    season_id: int,
    window: int = 5,
) -> pd.DataFrame:
    """Calculate rolling xG, xA, and key actions over a match window.

    Football insight: Detect form trends — is a player peaking or declining?
    Useful for rotation decisions and opponent analysis timing.
    """
    query = text("""
        SELECT
            e.match_id,
            m.match_date,
            SUM(e.xg) FILTER (WHERE e.event_type = 'Shot') AS match_xg,
            SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL) AS match_xa,
            COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots,
            COUNT(*) FILTER (WHERE e.key_pass) AS key_passes,
            COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures
        FROM events e
        JOIN matches m ON e.match_id = m.match_id
        WHERE e.player_id = :player_id
          AND m.season_id = :season_id
        GROUP BY e.match_id, m.match_date
        ORDER BY m.match_date
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"player_id": player_id, "season_id": season_id})

    if df.empty:
        return df

    # Compute rolling averages (vectorised with pandas)
    df["rolling_xg"] = df["match_xg"].rolling(window=window, min_periods=1).mean()
    df["rolling_xa"] = df["match_xa"].rolling(window=window, min_periods=1).mean()
    df["rolling_shots"] = df["shots"].rolling(window=window, min_periods=1).mean()

    return df


def get_player_radar_percentiles(
    engine: Engine,
    player_id: int,
    season_id: int,
) -> pd.DataFrame:
    """Compute percentile ranks for radar chart visualisation.

    Compares the player against all players in the same season.
    Football insight: Quickly compare players across multiple dimensions
    for recruitment shortlisting.
    """
    # Get all player summaries for the season
    query = text("""
        SELECT
            e.player_id,
            COUNT(DISTINCT e.match_id) AS appearances,
            COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0) /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS xg_per_match,
            COALESCE(SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL), 0) /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS xa_per_match,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL)::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS passes_per_match,
            COUNT(*) FILTER (WHERE e.event_type = 'Dribble' AND e.dribble_outcome = 'Complete')::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS dribbles_per_match,
            COUNT(*) FILTER (WHERE e.event_type = 'Pressure')::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS pressures_per_match,
            COUNT(*) FILTER (WHERE e.event_type IN ('Tackle', 'Interception'))::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS def_actions_per_match
        FROM events e
        JOIN matches m ON e.match_id = m.match_id
        WHERE m.season_id = :season_id
          AND e.player_id IS NOT NULL
        GROUP BY e.player_id
        HAVING COUNT(DISTINCT e.match_id) >= 3
    """)
    with engine.connect() as conn:
        all_players = pd.read_sql(query, conn, params={"season_id": season_id})

    if all_players.empty or player_id not in all_players["player_id"].values:
        return pd.DataFrame()

    # Calculate percentile ranks
    metrics = ["xg_per_match", "xa_per_match", "passes_per_match",
               "dribbles_per_match", "pressures_per_match", "def_actions_per_match"]

    player_row = all_players[all_players["player_id"] == player_id].iloc[0]
    percentiles = {}
    for metric in metrics:
        rank = (all_players[metric] <= player_row[metric]).mean()
        percentiles[metric] = round(rank * 100, 1)

    return pd.DataFrame([percentiles])


def get_squad_comparison(
    engine: Engine,
    team_id: int,
    season_id: int,
) -> pd.DataFrame:
    """Compare all squad players on key per-90 metrics.

    Football insight: Identify over/under-performers relative to xG,
    find players contributing most without scoring, etc.
    """
    query = text("""
        SELECT
            p.player_name,
            COUNT(DISTINCT e.match_id) AS appearances,
            ROUND(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot')::NUMERIC, 2) AS total_xg,
            COUNT(*) FILTER (WHERE e.shot_outcome = 'Goal') AS goals,
            ROUND(SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL)::NUMERIC, 2) AS total_xa,
            COUNT(*) FILTER (WHERE e.assist) AS assists,
            COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures,
            COUNT(*) FILTER (WHERE e.key_pass) AS key_passes
        FROM events e
        JOIN players p ON e.player_id = p.player_id
        JOIN matches m ON e.match_id = m.match_id
        WHERE e.team_id = :team_id
          AND m.season_id = :season_id
          AND e.player_id IS NOT NULL
        GROUP BY p.player_name
        HAVING COUNT(DISTINCT e.match_id) >= 2
        ORDER BY total_xg DESC NULLS LAST
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"team_id": team_id, "season_id": season_id})
