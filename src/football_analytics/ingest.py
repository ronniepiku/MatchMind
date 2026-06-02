"""Data ingestion pipeline for StatsBomb open data.

Downloads events and lineups via statsbombpy, normalizes the nested JSON
into relational tables, and bulk-loads into PostgreSQL.

Performance notes:
- Uses pandas for vectorised normalisation (avoid row-level loops).
- COPY protocol via psycopg2 copy_expert for maximum bulk load speed.
- Fallback to executemany for environments without COPY support.
- Idempotent: uses staging table + INSERT ... ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from statsbombpy import sb
from tqdm import tqdm

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)


# =============================================================================
# DATA FETCHING (StatsBomb Open Data via statsbombpy)
# =============================================================================


def fetch_competitions() -> pd.DataFrame:
    """Fetch all available competitions from StatsBomb open data."""
    df = sb.competitions()
    logger.info("Fetched %d competition-season combinations", len(df))
    return df


def fetch_matches(competition_id: int, season_id: int) -> pd.DataFrame:
    """Fetch matches for a given competition and season."""
    df = sb.matches(competition_id=competition_id, season_id=season_id)
    logger.info(
        "Fetched %d matches for competition=%d season=%d",
        len(df),
        competition_id,
        season_id,
    )
    return df


def fetch_events(match_id: int) -> pd.DataFrame:
    """Fetch all events for a single match.

    Returns a flat DataFrame with nested fields already extracted by statsbombpy.
    """
    df = sb.events(match_id=match_id)
    logger.debug("Fetched %d events for match %d", len(df), match_id)
    return df


def fetch_lineups(match_id: int) -> dict[str, pd.DataFrame]:
    """Fetch lineup data for a match (returns dict of team_name -> DataFrame)."""
    return sb.lineups(match_id=match_id)


# =============================================================================
# DATA NORMALISATION
# =============================================================================


def normalize_events(raw_events: pd.DataFrame, match_id: int) -> pd.DataFrame:
    """Transform raw StatsBomb events into our schema format.

    Key transformations:
    - Extract location coordinates from nested lists.
    - Map StatsBomb column names to our schema columns.
    - Generate deterministic UUIDs for event_id if missing.
    - Vectorised operations for performance (no iterrows).
    """
    df = raw_events.copy()

    # Rename core columns
    # statsbombpy uses short names (type, team, player);
    # json_normalize on raw JSON uses nested names (type_name, team_name, player_name)
    col_map: dict[str, str] = {
        "id": "event_id",
        "type": "event_type",
        "type_name": "event_type",
        "team": "team_name",
        "team_name": "team_name",
        "player": "player_name",
        "player_name": "player_name",
        "period": "period",
        "timestamp": "timestamp",
        "minute": "minute",
        "second": "second",
        "possession": "possession",
        "possession_team": "possession_team_name",
        "possession_team_name": "possession_team_name",
        "play_pattern": "play_pattern",
        "play_pattern_name": "play_pattern",
        "duration": "duration",
        "under_pressure": "under_pressure",
    }
    # Only rename columns that exist
    existing_renames = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=existing_renames)

    # Generate event UUIDs if missing (StatsBomb open data may omit explicit event_id)
    if "event_id" not in df.columns or df["event_id"].isnull().any():
        if "id" in raw_events.columns:
            generated_ids = (
                raw_events["id"]
                .astype(str)
                .apply(
                    lambda raw_id: str(
                        uuid.uuid5(uuid.NAMESPACE_URL, f"{match_id}-{raw_id}")
                    )
                )
            )
        else:
            generated_ids = [str(uuid.uuid4()) for _ in range(len(df))]

        if "event_id" in df.columns:
            df["event_id"] = df["event_id"].fillna(generated_ids)
        else:
            df["event_id"] = generated_ids

    # Extract location coordinates (vectorised)
    if "location" in df.columns:
        locations = df["location"].apply(
            lambda loc: pd.Series(
                loc if isinstance(loc, list) and len(loc) >= 2 else [None, None]
            )
        )
        df["location_x"] = locations[0].astype("Float64")
        df["location_y"] = locations[1].astype("Float64")
    else:
        df["location_x"] = None
        df["location_y"] = None

    # Shot fields
    if "shot_statsbomb_xg" in df.columns:
        df["xg"] = df["shot_statsbomb_xg"].astype("Float64")
    elif "shot_xg" in df.columns:
        df["xg"] = df["shot_xg"].astype("Float64")
    else:
        df["xg"] = None

    # Pass fields (vectorised extraction)
    for col in ["pass_length", "pass_angle"]:
        if col not in df.columns:
            df[col] = None

    # Ensure match_id is set
    df["match_id"] = match_id

    # Fill boolean defaults
    for bool_col in ["under_pressure", "counterpress", "key_pass", "assist"]:
        if bool_col in df.columns:
            df[bool_col] = df[bool_col].fillna(False).astype(bool)
        else:
            df[bool_col] = False

    return df


def normalize_lineups(
    lineups_dict: dict[str, pd.DataFrame],
    match_id: int,
    team_id_map: dict[str, int],
) -> pd.DataFrame:
    """Flatten lineup dicts into a single DataFrame matching our schema."""
    records: list[dict[str, Any]] = []
    for team_name, lineup_df in lineups_dict.items():
        team_id = team_id_map.get(team_name, 0)
        for _, row in lineup_df.iterrows():
            records.append(
                {
                    "match_id": match_id,
                    "team_id": team_id,
                    "player_id": row.get("player_id"),
                    "player_name": row.get("player_name"),
                    "jersey_number": row.get("jersey_number"),
                    "position": (
                        row.get("positions", [{}])[0].get("position")
                        if row.get("positions")
                        else None
                    ),
                    "is_starter": (
                        row.get("positions", [{}])[0].get("from", "0:00:00")
                        == "0:00:00"
                        if row.get("positions")
                        else False
                    ),
                }
            )
    return pd.DataFrame(records)


# =============================================================================
# DATABASE LOADING
# =============================================================================


def init_schema(engine: Engine) -> None:
    """Execute the DDL schema file to create tables and indexes."""
    from pathlib import Path

    schema_path = Path(__file__).parent / "db" / "schema.sql"
    ddl = schema_path.read_text(encoding="utf-8")

    with engine.begin() as conn:
        conn.execute(text(ddl))
    logger.info("Schema initialised successfully")


def bulk_load_teams(engine: Engine, teams: pd.DataFrame) -> None:
    """Upsert teams into the database."""
    if teams.empty:
        return
    with engine.begin() as conn:
        for _, row in teams.iterrows():
            conn.execute(
                text("""
                    INSERT INTO teams (team_id, team_name)
                    VALUES (:team_id, :team_name)
                    ON CONFLICT (team_id) DO NOTHING
                """),
                {"team_id": int(row["team_id"]), "team_name": row["team_name"]},
            )


def bulk_load_players(engine: Engine, players: pd.DataFrame) -> None:
    """Upsert players into the database."""
    if players.empty:
        return
    records = players[["player_id", "player_name"]].drop_duplicates().to_dict("records")
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO players (player_id, player_name)
                VALUES (:player_id, :player_name)
                ON CONFLICT (player_id) DO NOTHING
            """),
            records,
        )


def bulk_load_events(engine: Engine, events_df: pd.DataFrame) -> None:
    """Bulk load events using PostgreSQL COPY protocol for maximum throughput.

    Performance: COPY is 5-10x faster than executemany for large batches.
    Uses a staging table approach for idempotent upserts:
    1. COPY data into a temp staging table (no constraints)
    2. INSERT INTO events ... SELECT FROM staging ON CONFLICT DO NOTHING
    3. DROP staging table

    Fallback: If COPY fails (e.g., connection type issues), falls back to
    executemany with batch_size=1000.
    """
    if events_df.empty:
        return

    # Select only columns that exist in our schema
    schema_cols = [
        "event_id",
        "match_id",
        "team_id",
        "player_id",
        "event_type",
        "period",
        "timestamp",
        "minute",
        "second",
        "possession",
        "possession_team_id",
        "play_pattern",
        "location_x",
        "location_y",
        "duration",
        "under_pressure",
        "xg",
        "shot_outcome",
        "pass_length",
        "pass_angle",
        "pass_outcome",
        "pass_recipient_id",
        "key_pass",
        "assist",
        "xa",
        "counterpress",
    ]
    available_cols = [c for c in schema_cols if c in events_df.columns]
    insert_df = events_df[available_cols].copy()

    # Replace NaN with None for proper NULL handling
    insert_df = insert_df.where(pd.notnull(insert_df), None)

    try:
        _copy_load_events(engine, insert_df, available_cols)
    except Exception as e:
        logger.warning("COPY protocol failed (%s), falling back to executemany", e)
        _executemany_load_events(engine, insert_df, available_cols)

    logger.info("Loaded %d events", len(insert_df))


def _copy_load_events(engine: Engine, df: pd.DataFrame, cols: list[str]) -> None:
    """Load events via PostgreSQL COPY protocol (fastest path).

    Uses StringIO buffer to stream CSV data directly into Postgres,
    bypassing SQL parsing overhead entirely.
    """
    # Serialize DataFrame to CSV in-memory buffer
    buffer = io.StringIO()
    df.to_csv(
        buffer,
        index=False,
        header=False,
        sep="\t",
        na_rep="\\N",
        quoting=csv.QUOTE_NONE,
        escapechar="\\",
    )
    buffer.seek(0)

    cols_str = ", ".join(cols)

    # Get raw psycopg2 connection for COPY support
    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        # Create temp staging table
        cursor.execute("""
            CREATE TEMP TABLE _staging_events (LIKE events INCLUDING NOTHING)
            ON COMMIT DROP
        """)
        # COPY into staging
        cursor.copy_expert(
            f"COPY _staging_events ({cols_str}) FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', NULL '\\N')",
            buffer,
        )
        # Upsert from staging to events
        cursor.execute(f"""
            INSERT INTO events ({cols_str})
            SELECT {cols_str} FROM _staging_events
            ON CONFLICT (event_id) DO NOTHING
        """)
        raw_conn.commit()
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()


def _executemany_load_events(engine: Engine, df: pd.DataFrame, cols: list[str]) -> None:
    """Fallback: load events via executemany (slower but more compatible)."""
    cols_str = ", ".join(cols)
    params_str = ", ".join(f":{c}" for c in cols)
    sql = f"INSERT INTO events ({cols_str}) VALUES ({params_str}) ON CONFLICT (event_id) DO NOTHING"

    records = df.to_dict("records")
    with engine.begin() as conn:
        conn.execute(text(sql), records)


# =============================================================================
# ORCHESTRATION
# =============================================================================


def ingest_competition(
    competition_id: int,
    season_id: int,
    engine: Engine | None = None,
    max_matches: int | None = None,
) -> None:
    """Full pipeline: fetch → normalize → load for a competition/season.

    Args:
        competition_id: StatsBomb competition ID.
        season_id: StatsBomb season ID.
        engine: SQLAlchemy engine (created if None).
        max_matches: Limit matches for testing/demo purposes.
    """
    if engine is None:
        engine = get_engine()

    # 1. Initialise schema
    init_schema(engine)

    # 2. Fetch matches
    matches_df = fetch_matches(competition_id, season_id)
    if max_matches:
        matches_df = matches_df.head(max_matches)

    # 3. Extract and load teams
    home_teams = matches_df[["home_team_id", "home_team"]].rename(
        columns={"home_team_id": "team_id", "home_team": "team_name"}
    )
    away_teams = matches_df[["away_team_id", "away_team"]].rename(
        columns={"away_team_id": "team_id", "away_team": "team_name"}
    )
    all_teams = pd.concat([home_teams, away_teams]).drop_duplicates(subset=["team_id"])
    bulk_load_teams(engine, all_teams)

    # 4. Load competition metadata and matches
    _load_competition(engine, matches_df, competition_id, season_id)
    _load_matches(engine, matches_df, competition_id, season_id)

    # 5. Process each match (events + lineups)
    team_id_map = dict(zip(all_teams["team_name"], all_teams["team_id"]))

    for _, match_row in tqdm(
        matches_df.iterrows(), total=len(matches_df), desc="Ingesting matches"
    ):
        match_id = int(match_row["match_id"])
        try:
            # Fetch and load events
            raw_events = fetch_events(match_id)
            events = normalize_events(raw_events, match_id)

            # Extract and load players from events
            players = _extract_players_from_events(raw_events)
            bulk_load_players(engine, players)

            # Map team/player names to IDs and load events
            events = _resolve_ids(events, engine)
            bulk_load_events(engine, events)

            # Fetch and load lineups
            lineups_raw = fetch_lineups(match_id)
            lineups = normalize_lineups(lineups_raw, match_id, team_id_map)
            _load_lineups(engine, lineups)

        except Exception as e:
            logger.warning("Failed to process match %d: %s", match_id, e)
            continue

    # 6. Refresh materialised views for fresh dashboard/API data
    _refresh_materialised_views(engine)

    logger.info(
        "Ingestion complete for competition=%d season=%d", competition_id, season_id
    )


def _refresh_materialised_views(engine: Engine) -> None:
    """Refresh materialised views after ingestion for data freshness."""
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT refresh_materialised_views()"))
        logger.info("Materialised views refreshed successfully")
    except Exception as e:
        logger.warning(
            "Could not refresh materialised views: %s. "
            "Dashboard data may be stale until manually refreshed.",
            e,
        )


def _load_competition(
    engine: Engine, matches_df: pd.DataFrame, competition_id: int, season_id: int
) -> None:
    """Load the competition/season row required by match foreign keys."""
    if matches_df.empty:
        return

    first_row = matches_df.iloc[0]
    competition_name = first_row.get("competition_name") or "Unknown Competition"
    season_name = first_row.get("season_name") or f"Season {season_id}"
    country_name = first_row.get("country_name")

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO competitions (
                    competition_id,
                    competition_name,
                    country_name,
                    season_id,
                    season_name
                )
                VALUES (
                    :competition_id,
                    :competition_name,
                    :country_name,
                    :season_id,
                    :season_name
                )
                ON CONFLICT (competition_id) DO NOTHING
            """),
            {
                "competition_id": competition_id,
                "competition_name": competition_name,
                "country_name": country_name,
                "season_id": season_id,
                "season_name": season_name,
            },
        )


def _load_matches(
    engine: Engine, matches_df: pd.DataFrame, competition_id: int, season_id: int
) -> None:
    """Load match records."""
    with engine.begin() as conn:
        for _, row in matches_df.iterrows():
            conn.execute(
                text("""
                    INSERT INTO matches (match_id, competition_id, season_id, match_date,
                                        home_team_id, away_team_id, home_score, away_score,
                                        match_week)
                    VALUES (:match_id, :competition_id, :season_id, :match_date,
                            :home_team_id, :away_team_id, :home_score, :away_score,
                            :match_week)
                    ON CONFLICT (match_id) DO NOTHING
                """),
                {
                    "match_id": int(row["match_id"]),
                    "competition_id": competition_id,
                    "season_id": season_id,
                    "match_date": row["match_date"],
                    "home_team_id": int(row["home_team_id"]),
                    "away_team_id": int(row["away_team_id"]),
                    "home_score": int(row.get("home_score", 0)),
                    "away_score": int(row.get("away_score", 0)),
                    "match_week": (
                        int(row.get("match_week", 0))
                        if pd.notnull(row.get("match_week"))
                        else None
                    ),
                },
            )


def _extract_players_from_events(raw_events: pd.DataFrame) -> pd.DataFrame:
    """Extract unique player IDs and names from event data."""
    if "player_id" not in raw_events.columns:
        return pd.DataFrame(columns=["player_id", "player_name"])
    # statsbombpy uses "player" column; json_normalize uses "player_name"
    if "player_name" in raw_events.columns:
        name_col = "player_name"
    elif "player" in raw_events.columns:
        name_col = "player"
    else:
        return pd.DataFrame(columns=["player_id", "player_name"])
    players = raw_events[["player_id", name_col]].dropna(subset=["player_id"]).copy()
    players = players.rename(columns={name_col: "player_name"})
    players["player_id"] = players["player_id"].astype(int)
    return players.drop_duplicates(subset=["player_id"])


def _resolve_ids(events: pd.DataFrame, engine: Engine) -> pd.DataFrame:
    """Resolve team/player name references to IDs.

    For simplicity with StatsBomb data, IDs are typically already present.
    This function ensures the team_id column is populated from team_name lookups.
    """
    # StatsBomb events usually have team_id directly via statsbombpy
    # If not present, do a lookup
    if "team_id" not in events.columns and "team_name" in events.columns:
        with engine.connect() as conn:
            teams = pd.read_sql("SELECT team_id, team_name FROM teams", conn)
        team_map = dict(zip(teams["team_name"], teams["team_id"]))
        events["team_id"] = events["team_name"].map(team_map)
    return events


def _load_lineups(engine: Engine, lineups: pd.DataFrame) -> None:
    """Bulk load lineup records."""
    if lineups.empty:
        return
    with engine.begin() as conn:
        for _, row in lineups.iterrows():
            if pd.isna(row.get("player_id")):
                continue
            conn.execute(
                text("""
                    INSERT INTO lineups (match_id, team_id, player_id, jersey_number,
                                        position, is_starter)
                    VALUES (:match_id, :team_id, :player_id, :jersey_number,
                            :position, :is_starter)
                    ON CONFLICT (match_id, team_id, player_id) DO NOTHING
                """),
                {
                    "match_id": int(row["match_id"]),
                    "team_id": int(row["team_id"]),
                    "player_id": int(row["player_id"]),
                    "jersey_number": (
                        int(row["jersey_number"])
                        if pd.notnull(row.get("jersey_number"))
                        else None
                    ),
                    "position": row.get("position"),
                    "is_starter": bool(row.get("is_starter", False)),
                },
            )


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main() -> None:
    """CLI entry point for data ingestion.

    Default: Ingests FIFA World Cup 2022 (competition_id=43, season_id=106)
    which is freely available in StatsBomb open data.
    """
    import argparse

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Ingest StatsBomb data into PostgreSQL"
    )
    parser.add_argument(
        "--competition-id",
        type=int,
        default=43,
        help="StatsBomb competition ID (default: 43 = World Cup)",
    )
    parser.add_argument(
        "--season-id",
        type=int,
        default=106,
        help="StatsBomb season ID (default: 106 = 2022)",
    )
    parser.add_argument(
        "--max-matches",
        type=int,
        default=None,
        help="Limit number of matches (for testing)",
    )
    args = parser.parse_args()

    ingest_competition(
        competition_id=args.competition_id,
        season_id=args.season_id,
        max_matches=args.max_matches,
    )


if __name__ == "__main__":
    main()
