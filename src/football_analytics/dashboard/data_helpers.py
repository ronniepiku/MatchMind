"""Data helpers for the dashboard — provides dropdown options and data availability checks.

Fetches available teams, seasons, and players from the database.
Falls back to StatsBomb open data when the database is empty or unreachable.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)


def get_available_teams(engine: Any) -> list[dict[str, str]]:
    """Fetch teams available in the database as dropdown options.

    Returns list of dicts with 'label' (team name) and 'value' (team_id).
    Falls back to StatsBomb if database is empty.
    """
    try:
        with engine.connect() as conn:
            df = pd.read_sql(
                text("SELECT team_id, team_name FROM teams ORDER BY team_name"),
                conn,
            )
        if not df.empty:
            return [
                {"label": row["team_name"], "value": row["team_id"]}
                for _, row in df.iterrows()
            ]
    except Exception as e:
        logger.warning("Could not fetch teams from DB: %s", e)

    # Fallback: fetch from StatsBomb open data
    return _get_statsbomb_teams()


def get_available_seasons(engine: Any) -> list[dict[str, str]]:
    """Fetch available competition/season combinations as dropdown options.

    Returns list of dicts with 'label' (e.g., "La Liga 2019/2020") and 'value' (season_id).
    """
    try:
        with engine.connect() as conn:
            df = pd.read_sql(
                text("""
                    SELECT DISTINCT c.season_id, c.season_name, c.competition_name
                    FROM competitions c
                    ORDER BY c.season_name DESC
                """),
                conn,
            )
        if not df.empty:
            return [
                {
                    "label": f"{row['competition_name']} — {row['season_name']}",
                    "value": row["season_id"],
                }
                for _, row in df.iterrows()
            ]
    except Exception as e:
        logger.warning("Could not fetch seasons from DB: %s", e)

    # Fallback: fetch from StatsBomb open data
    return _get_statsbomb_seasons()


def get_available_players(
    engine: Any,
    team_id: int | None = None,
    season_id: int | None = None,
) -> list[dict[str, str]]:
    """Fetch players available in the database as dropdown options.

    Optionally filtered by team and season.
    Returns list of dicts with 'label' (player name) and 'value' (player_id).
    """
    try:
        query = """
            SELECT DISTINCT p.player_id, p.player_name
            FROM players p
            JOIN events e ON e.player_id = p.player_id
            JOIN matches m ON e.match_id = m.match_id
            WHERE 1=1
        """
        params: dict = {}
        if team_id:
            query += " AND e.team_id = :team_id"
            params["team_id"] = team_id
        if season_id:
            query += " AND m.season_id = :season_id"
            params["season_id"] = season_id

        query += " ORDER BY p.player_name"

        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        if not df.empty:
            return [
                {"label": row["player_name"], "value": row["player_id"]}
                for _, row in df.iterrows()
            ]
    except Exception as e:
        logger.warning("Could not fetch players from DB: %s", e)

    return []


def check_data_availability(
    engine: Any,
    team_id: int,
    season_id: int,
) -> dict[str, bool | str]:
    """Check whether data exists for a given team/season combination.

    Returns a dict with availability status and a helpful message.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT COUNT(DISTINCT e.match_id) AS match_count
                    FROM events e
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE e.team_id = :team_id AND m.season_id = :season_id
                """),
                {"team_id": team_id, "season_id": season_id},
            ).fetchone()

        match_count = result[0] if result else 0
        if match_count > 0:
            return {
                "available": True,
                "message": f"{match_count} matches found",
                "match_count": match_count,
            }
        else:
            return {
                "available": False,
                "message": (
                    "No data found for this team/season. "
                    "Please run the data ingestion pipeline first: "
                    "uv run fb-ingest"
                ),
            }
    except Exception as e:
        return {
            "available": False,
            "message": (
                f"Database connection error: {e}. "
                "Ensure PostgreSQL is running and configured."
            ),
        }


def _get_statsbomb_teams() -> list[dict[str, str]]:
    """Get teams from StatsBomb open data as fallback."""
    try:
        from statsbombpy import sb

        # Use a popular competition to get teams
        matches = sb.matches(
            competition_id=11,
            season_id=106,
        )  # La Liga 2019/2020
        home = matches[["home_team_id", "home_team"]].rename(
            columns={"home_team_id": "team_id", "home_team": "team_name"},
        )
        away = matches[["away_team_id", "away_team"]].rename(
            columns={"away_team_id": "team_id", "away_team": "team_name"},
        )
        teams = (
            pd.concat([home, away])
            .drop_duplicates(subset=["team_id"])
            .sort_values("team_name")
        )
        return [
            {"label": row["team_name"], "value": row["team_id"]}
            for _, row in teams.iterrows()
        ]
    except Exception as e:
        logger.warning("StatsBomb fallback failed: %s", e)
        return []


def _get_statsbomb_seasons() -> list[dict[str, str]]:
    """Get seasons from StatsBomb open data as fallback."""
    try:
        from statsbombpy import sb

        competitions = sb.competitions()
        options = []
        for _, row in competitions.iterrows():
            options.append(
                {
                    "label": f"{row['competition_name']} — {row['season_name']}",
                    "value": row["season_id"],
                }
            )
        # Deduplicate by season_id and sort
        seen = set()
        unique_options = []
        for opt in options:
            key = (opt["label"], opt["value"])
            if key not in seen:
                seen.add(key)
                unique_options.append(opt)
        return sorted(unique_options, key=lambda x: x["label"])
    except Exception as e:
        logger.warning("StatsBomb fallback failed: %s", e)
        return []
