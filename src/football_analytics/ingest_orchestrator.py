"""Multi-competition ingestion orchestrator.

Extends the base ingestion pipeline to support:
- Multiple competitions simultaneously (PL, CL, World Cup, etc.)
- Incremental delta ingestion (only new matches since last sync)
- Competition registry with sync status tracking
- CLI interface: `fb-ingest --competition "World Cup 2026"` or `--all-active`
- Automatic team rating updates after ingestion

Usage:
    orchestrator = IngestionOrchestrator(engine)
    orchestrator.register_competition(competition_id=43, season_id=106, name="World Cup 2026")
    orchestrator.sync_all()  # Incremental sync of all active competitions
    orchestrator.sync_competition(competition_id=43, season_id=106)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)


@dataclass
class CompetitionRegistry:
    """Tracks which competitions are active and their sync status."""

    competition_id: int
    season_id: int
    competition_name: str
    country: str = ""
    is_active: bool = True
    last_sync: datetime | None = None
    matches_synced: int = 0
    total_matches: int = 0
    priority: int = 1  # 1 = highest


class IngestionOrchestrator:
    """Orchestrates multi-competition data ingestion.

    Manages the competition registry, detects new matches, and runs
    incremental ingestion across all active competitions.
    """

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def register_competition(
        self,
        competition_id: int,
        season_id: int,
        name: str,
        country: str = "",
        priority: int = 1,
    ) -> None:
        """Register a competition for ingestion tracking.

        Args:
            competition_id: StatsBomb competition ID.
            season_id: StatsBomb season ID.
            name: Human-readable competition name.
            country: Country/region.
            priority: Ingestion priority (1 = highest).
        """
        query = text("""
            INSERT INTO competition_registry
                (competition_id, season_id, competition_name, country, priority, is_active)
            VALUES (:cid, :sid, :name, :country, :priority, TRUE)
            ON CONFLICT (competition_id, season_id) DO UPDATE
                SET competition_name = :name, country = :country,
                    priority = :priority, is_active = TRUE
        """)

        with self._engine.begin() as conn:
            conn.execute(
                query,
                {
                    "cid": competition_id,
                    "sid": season_id,
                    "name": name,
                    "country": country,
                    "priority": priority,
                },
            )
        logger.info("Registered competition: %s (%d/%d)", name, competition_id, season_id)

    def deactivate_competition(self, competition_id: int, season_id: int) -> None:
        """Mark a competition as inactive (won't be synced)."""
        query = text("""
            UPDATE competition_registry SET is_active = FALSE
            WHERE competition_id = :cid AND season_id = :sid
        """)
        with self._engine.begin() as conn:
            conn.execute(query, {"cid": competition_id, "sid": season_id})

    def get_active_competitions(self) -> list[CompetitionRegistry]:
        """Get all active competitions ordered by priority."""
        query = text("""
            SELECT competition_id, season_id, competition_name, country,
                   is_active, last_sync, matches_synced, total_matches, priority
            FROM competition_registry
            WHERE is_active = TRUE
            ORDER BY priority ASC, competition_name ASC
        """)

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(query, conn)
        except Exception:
            return []

        return [
            CompetitionRegistry(
                competition_id=int(row["competition_id"]),
                season_id=int(row["season_id"]),
                competition_name=row["competition_name"],
                country=row.get("country") or "",
                is_active=bool(row["is_active"]),
                last_sync=row.get("last_sync"),
                matches_synced=int(row.get("matches_synced") or 0),
                total_matches=int(row.get("total_matches") or 0),
                priority=int(row.get("priority") or 1),
            )
            for _, row in df.iterrows()
        ]

    def get_sync_status(self) -> list[dict[str, Any]]:
        """Get sync status summary for all active competitions."""
        comps = self.get_active_competitions()
        return [
            {
                "competition_name": c.competition_name,
                "competition_id": c.competition_id,
                "season_id": c.season_id,
                "matches_synced": c.matches_synced,
                "total_matches": c.total_matches,
                "last_sync": c.last_sync.isoformat() if c.last_sync else None,
                "is_complete": c.matches_synced >= c.total_matches and c.total_matches > 0,
                "priority": c.priority,
            }
            for c in comps
        ]

    def sync_all(self, force: bool = False) -> dict[str, Any]:
        """Sync all active competitions (incremental).

        Args:
            force: If True, re-ingest all matches even if already synced.

        Returns:
            Summary of sync operation.
        """
        competitions = self.get_active_competitions()
        results = []

        for comp in competitions:
            try:
                result = self.sync_competition(comp.competition_id, comp.season_id, force=force)
                results.append(result)
            except Exception as exc:
                logger.error(f"Failed to sync {comp.competition_name}: {exc}")
                results.append(
                    {
                        "competition_name": comp.competition_name,
                        "status": "error",
                        "error": str(exc),
                    }
                )

        return {
            "competitions_processed": len(results),
            "successful": sum(1 for r in results if r.get("status") != "error"),
            "failed": sum(1 for r in results if r.get("status") == "error"),
            "details": results,
        }

    def sync_competition(
        self,
        competition_id: int,
        season_id: int,
        force: bool = False,
    ) -> dict[str, Any]:
        """Sync a single competition (incremental).

        Detects new matches not yet in the database and ingests only those.

        Args:
            competition_id: Competition to sync.
            season_id: Season to sync.
            force: Re-ingest all matches.

        Returns:
            Sync result summary.
        """
        from football_analytics.ingest import (
            fetch_matches,
            ingest_full_pipeline,
        )

        # Fetch available matches from StatsBomb
        available_matches = fetch_matches(competition_id, season_id)
        total_available = len(available_matches)

        # Determine which matches are already ingested
        if not force:
            existing_ids = self._get_existing_match_ids(competition_id, season_id)
            new_matches = available_matches[~available_matches["match_id"].isin(existing_ids)]
        else:
            new_matches = available_matches

        new_count = len(new_matches)
        if new_count == 0:
            logger.info(f"Competition {competition_id}/{season_id}: already up to date.")
            self._update_sync_status(competition_id, season_id, total_available, total_available)
            return {
                "competition_id": competition_id,
                "season_id": season_id,
                "status": "up_to_date",
                "new_matches": 0,
                "total_matches": total_available,
            }

        logger.info(
            f"Competition {competition_id}/{season_id}: ingesting {new_count} new matches "
            f"(total available: {total_available})"
        )

        # Run ingestion for new matches only
        ingested = 0
        errors = []
        for _, match_row in new_matches.iterrows():
            match_id = int(match_row["match_id"])
            try:
                ingest_full_pipeline(
                    competition_id=competition_id,
                    season_id=season_id,
                    match_ids=[match_id],
                )
                ingested += 1
            except Exception as exc:
                logger.warning(f"Failed to ingest match {match_id}: {exc}")
                errors.append({"match_id": match_id, "error": str(exc)})

        # Update registry
        synced_total = (total_available - new_count) + ingested
        self._update_sync_status(competition_id, season_id, synced_total, total_available)

        # Trigger rating update for new data
        self._trigger_rating_update(competition_id, season_id)

        return {
            "competition_id": competition_id,
            "season_id": season_id,
            "status": "synced",
            "new_matches": ingested,
            "errors": len(errors),
            "total_matches": total_available,
            "error_details": errors if errors else None,
        }

    def discover_competitions(self) -> list[dict[str, Any]]:
        """Discover available competitions from StatsBomb open data.

        Returns list of competitions available for registration.
        """
        from football_analytics.ingest import fetch_competitions

        df = fetch_competitions()
        return [
            {
                "competition_id": int(row["competition_id"]),
                "season_id": int(row["season_id"]),
                "competition_name": row.get("competition_name", ""),
                "season_name": row.get("season_name", ""),
                "country_name": row.get("country_name", ""),
            }
            for _, row in df.iterrows()
        ]

    def _get_existing_match_ids(self, competition_id: int, season_id: int) -> set[int]:
        """Get match IDs already in the database for this competition."""
        query = text("""
            SELECT match_id FROM matches
            WHERE competition_id = :cid AND season_id = :sid
        """)
        try:
            with self._engine.connect() as conn:
                result = conn.execute(query, {"cid": competition_id, "sid": season_id})
                return {row[0] for row in result}
        except Exception:
            return set()

    def _update_sync_status(
        self,
        competition_id: int,
        season_id: int,
        matches_synced: int,
        total_matches: int,
    ) -> None:
        """Update the sync status in the registry."""
        query = text("""
            UPDATE competition_registry
            SET last_sync = NOW(), matches_synced = :synced, total_matches = :total
            WHERE competition_id = :cid AND season_id = :sid
        """)
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    query,
                    {
                        "cid": competition_id,
                        "sid": season_id,
                        "synced": matches_synced,
                        "total": total_matches,
                    },
                )
        except Exception as exc:
            logger.warning(f"Failed to update sync status: {exc}")

    def _trigger_rating_update(self, competition_id: int, season_id: int) -> None:
        """Trigger team rating update after new data is ingested."""
        try:
            from football_analytics.prediction.team_rating import TeamRatingEngine

            engine = TeamRatingEngine(engine=self._engine)
            engine.compute_ratings(competition_ids=[competition_id])
            logger.info(f"Team ratings updated for competition {competition_id}")
        except Exception as exc:
            logger.warning(f"Rating update failed (non-critical): {exc}")


# ─── Schema additions ──────────────────────────────────────────────────────

COMPETITION_REGISTRY_DDL = """
CREATE TABLE IF NOT EXISTS competition_registry (
    competition_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    competition_name TEXT NOT NULL,
    country TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT TRUE,
    last_sync TIMESTAMPTZ,
    matches_synced INTEGER DEFAULT 0,
    total_matches INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (competition_id, season_id)
);
"""


def ensure_registry_table(engine: Engine | None = None) -> None:
    """Create the competition_registry table if it doesn't exist."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        conn.execute(text(COMPETITION_REGISTRY_DDL))


# ─── CLI Entry Point ───────────────────────────────────────────────────────


def main() -> None:
    """CLI for multi-competition ingestion.

    Usage:
        python -m football_analytics.ingest_orchestrator --sync-all
        python -m football_analytics.ingest_orchestrator --competition 43 --season 106
        python -m football_analytics.ingest_orchestrator --discover
        python -m football_analytics.ingest_orchestrator --status
    """
    import argparse

    parser = argparse.ArgumentParser(description="MatchMind multi-competition ingestion")
    parser.add_argument("--sync-all", action="store_true", help="Sync all active competitions")
    parser.add_argument("--competition", type=int, help="Competition ID to sync")
    parser.add_argument("--season", type=int, help="Season ID to sync")
    parser.add_argument("--force", action="store_true", help="Force full re-ingestion")
    parser.add_argument("--discover", action="store_true", help="List available competitions")
    parser.add_argument("--status", action="store_true", help="Show sync status")
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register a competition (requires --competition, --season, --name)",
    )
    parser.add_argument("--name", type=str, help="Competition name for registration")

    args = parser.parse_args()
    orchestrator = IngestionOrchestrator()

    if args.discover:
        comps = orchestrator.discover_competitions()
        print(f"\n{'Competition':<30} {'Season':<15} {'Country':<15} {'IDs'}")
        print("-" * 80)
        for c in comps[:50]:
            print(
                f"{c['competition_name']:<30} {c['season_name']:<15} {c['country_name']:<15} {c['competition_id']}/{c['season_id']}"
            )

    elif args.status:
        statuses = orchestrator.get_sync_status()
        print(f"\n{'Competition':<30} {'Synced':<10} {'Total':<10} {'Last Sync':<20} {'Status'}")
        print("-" * 90)
        for s in statuses:
            status = "✓ Complete" if s["is_complete"] else "△ Partial"
            print(
                f"{s['competition_name']:<30} {s['matches_synced']:<10} {s['total_matches']:<10} {s['last_sync'] or 'Never':<20} {status}"
            )

    elif args.register and args.competition and args.season and args.name:
        orchestrator.register_competition(
            competition_id=args.competition,
            season_id=args.season,
            name=args.name,
        )
        print(f"Registered: {args.name} ({args.competition}/{args.season})")

    elif args.sync_all:
        result = orchestrator.sync_all(force=args.force)
        print(f"\nSync complete: {result['successful']} successful, {result['failed']} failed")
        for d in result["details"]:
            print(
                f"  {d.get('competition_id', '?')}/{d.get('season_id', '?')}: {d.get('status', 'unknown')} ({d.get('new_matches', 0)} new)"
            )

    elif args.competition and args.season:
        result = orchestrator.sync_competition(args.competition, args.season, force=args.force)
        print(f"\n{result['status']}: {result.get('new_matches', 0)} new matches ingested")
        if result.get("errors"):
            print(f"  Errors: {result['errors']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
