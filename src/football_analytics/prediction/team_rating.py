"""Team strength rating system — competition-agnostic time-weighted ratings.

Computes team offensive and defensive strength from historical event data.
Ratings are time-decayed (recent matches weighted higher), competition-weighted
(elite competitions valued over friendlies), and incrementally updatable.

Used by MatchPredictor to derive expected xG inputs for Monte Carlo simulation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)


class CompetitionTier(Enum):
    """Competition importance weighting for rating calculations."""

    ELITE = 1.0  # World Cup, Champions League knockout, top-5 league
    HIGH = 0.85  # Champions League group, Europa League, World Cup qualifiers
    MEDIUM = 0.7  # Second-tier leagues, domestic cups
    LOW = 0.5  # Friendlies, minor tournaments


# Default tier mapping (competition_id → tier)
# Users can override via configure_competition_tiers()
_DEFAULT_TIERS: dict[int, CompetitionTier] = {}


@dataclass
class TeamRating:
    """Computed strength rating for a team."""

    team_id: int
    team_name: str
    # Core metrics (per-90 basis)
    offensive_strength: float  # xG created per 90
    defensive_strength: float  # xG conceded per 90 (lower = better)
    # Derived
    overall_rating: float  # offensive - defensive (net xG per 90)
    # Supplementary
    pressing_intensity: float  # Pressures per 90
    possession_dominance: float  # Average possession share
    set_piece_threat: float  # Set-piece xG per 90
    directness: float  # Progressive carries + passes per 90
    # Metadata
    matches_used: int
    confidence: str  # "low" (<5 matches), "medium" (5-15), "high" (>15)
    form_trend: float  # Slope of last 5 matches overall rating
    last_match_date: date | None = None
    competition_ids: list[int] = field(default_factory=list)

    @property
    def is_reliable(self) -> bool:
        """Whether this rating has enough data to be trustworthy."""
        return self.matches_used >= 5


@dataclass
class TeamRatingSnapshot:
    """A point-in-time snapshot of all team ratings (for versioning)."""

    computed_at: date
    lookback_days: int
    n_teams: int
    ratings: dict[int, TeamRating]
    model_version: str = "v1.0"


class TeamRatingEngine:
    """Computes and manages team strength ratings.

    Ratings are derived from per-match xG and defensive metrics,
    weighted by time decay and competition importance.

    Usage:
        engine = TeamRatingEngine(db_engine)
        ratings = engine.compute_ratings()
        argentina = ratings[771]  # TeamRating for Argentina
        predictor.predict(team_a=771, team_b=773, ratings=ratings)
    """

    def __init__(
        self,
        engine: Engine | None = None,
        half_life_days: int = 180,
        competition_tiers: dict[int, CompetitionTier] | None = None,
    ):
        """Initialise the rating engine.

        Args:
            engine: SQLAlchemy database engine. Uses default if None.
            half_life_days: Exponential decay half-life in days.
                Default 180 days — a match 6 months ago has half the weight
                of today's match.
            competition_tiers: Optional mapping of competition_id to tier.
                If not provided, all competitions weighted equally.
        """
        self._engine = engine or get_engine()
        self._half_life_days = half_life_days
        self._competition_tiers = competition_tiers or _DEFAULT_TIERS

    def configure_competition_tiers(self, tiers: dict[int, CompetitionTier]) -> None:
        """Set competition importance weightings.

        Args:
            tiers: Mapping of competition_id to CompetitionTier.
                   Competitions not in this dict use MEDIUM tier.
        """
        self._competition_tiers = tiers

    def compute_ratings(
        self,
        competition_ids: list[int] | None = None,
        season_ids: list[int] | None = None,
        lookback_matches: int | None = None,
        reference_date: date | None = None,
    ) -> dict[int, TeamRating]:
        """Compute team ratings from historical match data.

        Args:
            competition_ids: Filter to specific competitions. None = all.
            season_ids: Filter to specific seasons. None = all.
            lookback_matches: Maximum matches per team to consider.
                If None, uses all available (with time decay handling recency).
            reference_date: Date from which to compute decay.
                Default = today.

        Returns:
            Dict mapping team_id to TeamRating.
        """
        ref_date = reference_date or date.today()
        team_matches = self._fetch_team_match_data(
            competition_ids, season_ids, lookback_matches
        )

        if team_matches.empty:
            logger.warning("No match data found for rating computation")
            return {}

        ratings: dict[int, TeamRating] = {}
        for team_id, group in team_matches.groupby("team_id"):
            rating = self._compute_single_team_rating(int(team_id), group, ref_date)
            if rating is not None:
                ratings[int(team_id)] = rating

        logger.info(f"Computed ratings for {len(ratings)} teams")
        return ratings

    def compute_ratings_snapshot(
        self,
        competition_ids: list[int] | None = None,
        season_ids: list[int] | None = None,
    ) -> TeamRatingSnapshot:
        """Compute a versioned snapshot of all ratings."""
        ratings = self.compute_ratings(
            competition_ids=competition_ids, season_ids=season_ids
        )
        return TeamRatingSnapshot(
            computed_at=date.today(),
            lookback_days=self._half_life_days * 3,
            n_teams=len(ratings),
            ratings=ratings,
        )

    def _fetch_team_match_data(
        self,
        competition_ids: list[int] | None,
        season_ids: list[int] | None,
        lookback_matches: int | None,
    ) -> pd.DataFrame:
        """Fetch per-team, per-match aggregated metrics from database."""
        filters = []
        params: dict[str, Any] = {}

        if competition_ids:
            filters.append("m.competition_id = ANY(:comp_ids)")
            params["comp_ids"] = competition_ids
        if season_ids:
            filters.append("m.season_id = ANY(:season_ids)")
            params["season_ids"] = season_ids

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        # Build lateral query for both teams per match
        query = text(f"""
            WITH match_team_stats AS (
                SELECT
                    e.team_id,
                    t.team_name,
                    e.match_id,
                    m.match_date,
                    m.competition_id,
                    m.home_team_id,
                    m.away_team_id,
                    -- Offensive metrics
                    COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0) AS xg_created,
                    COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots,
                    COUNT(*) FILTER (WHERE e.event_type = 'Shot' AND e.shot_outcome = 'Goal') AS goals,
                    -- Possession & build-up
                    COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS passes_completed,
                    COUNT(*) FILTER (WHERE e.event_type = 'Pass') AS passes_attempted,
                    COUNT(*) FILTER (WHERE e.event_type = 'Carry' AND
                        (e.carry_end_x - e.location_x) > 10) AS progressive_carries,
                    COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL AND
                        (e.end_location_x - e.location_x) > 10) AS progressive_passes,
                    -- Pressing
                    COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures,
                    COUNT(*) FILTER (WHERE e.counterpress) AS counterpresses,
                    -- Set pieces
                    COALESCE(SUM(e.xg) FILTER (
                        WHERE e.event_type = 'Shot' AND e.play_pattern IN ('From Corner', 'From Free Kick', 'From Throw In')
                    ), 0) AS set_piece_xg,
                    -- Total events for possession approximation
                    COUNT(*) AS total_events
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                JOIN teams t ON e.team_id = t.team_id
                {where_clause}
                GROUP BY e.team_id, t.team_name, e.match_id, m.match_date,
                         m.competition_id, m.home_team_id, m.away_team_id
            ),
            -- Get opponent xG for defensive rating
            opponent_xg AS (
                SELECT
                    a.team_id,
                    a.match_id,
                    b.xg_created AS xg_conceded
                FROM match_team_stats a
                JOIN match_team_stats b ON a.match_id = b.match_id AND a.team_id != b.team_id
            )
            SELECT
                mts.*,
                COALESCE(ox.xg_conceded, 0) AS xg_conceded
            FROM match_team_stats mts
            LEFT JOIN opponent_xg ox ON mts.team_id = ox.team_id AND mts.match_id = ox.match_id
            ORDER BY mts.team_id, mts.match_date DESC
        """)

        with self._engine.connect() as conn:
            df = pd.read_sql(query, conn, params=params)

        if lookback_matches and not df.empty:
            df = (
                df.sort_values(["team_id", "match_date"], ascending=[True, False])
                .groupby("team_id")
                .head(lookback_matches)
            )

        return df

    def _compute_single_team_rating(
        self,
        team_id: int,
        matches: pd.DataFrame,
        reference_date: date,
    ) -> TeamRating | None:
        """Compute rating for a single team from their match data."""
        if matches.empty:
            return None

        # Compute time-decay weights
        match_dates = pd.to_datetime(matches["match_date"]).dt.date
        days_ago = np.array([(reference_date - d).days for d in match_dates])
        time_weights = np.exp(-np.log(2) * days_ago / self._half_life_days)

        # Competition tier weights
        comp_weights = np.array(
            [self._get_competition_weight(cid) for cid in matches["competition_id"]]
        )

        # Combined weights
        weights = time_weights * comp_weights
        weight_sum = weights.sum()
        if weight_sum == 0:
            return None

        # Weighted averages of core metrics
        xg_created = float(np.average(matches["xg_created"], weights=weights))
        xg_conceded = float(np.average(matches["xg_conceded"], weights=weights))
        pressures = float(np.average(matches["pressures"], weights=weights))

        # Possession approximation (share of total events)
        total_events = matches["total_events"].values
        # Approximate: team events / (team events * 2) — rough proxy
        possession_share = (
            float(np.average(total_events / (total_events * 2), weights=weights))
            if total_events.sum() > 0
            else 0.5
        )

        set_piece_xg = float(np.average(matches["set_piece_xg"], weights=weights))

        progressive = (
            matches["progressive_carries"].values + matches["progressive_passes"].values
        )
        directness = float(np.average(progressive, weights=weights))

        # Form trend: slope of xG balance over last 5 matches
        recent = matches.head(5)
        if len(recent) >= 3:
            recent_balance = recent["xg_created"].values - recent["xg_conceded"].values
            x = np.arange(len(recent_balance))
            slope = float(np.polyfit(x, recent_balance, 1)[0])
        else:
            slope = 0.0

        # Confidence level
        n_matches = len(matches)
        if n_matches >= 15:
            confidence = "high"
        elif n_matches >= 5:
            confidence = "medium"
        else:
            confidence = "low"

        team_name = matches["team_name"].iloc[0]
        last_date = pd.to_datetime(matches["match_date"]).max().date()
        comp_ids = matches["competition_id"].unique().tolist()

        return TeamRating(
            team_id=team_id,
            team_name=team_name,
            offensive_strength=round(xg_created, 3),
            defensive_strength=round(xg_conceded, 3),
            overall_rating=round(xg_created - xg_conceded, 3),
            pressing_intensity=round(pressures, 1),
            possession_dominance=round(possession_share, 3),
            set_piece_threat=round(set_piece_xg, 3),
            directness=round(directness, 1),
            matches_used=n_matches,
            confidence=confidence,
            form_trend=round(slope, 3),
            last_match_date=last_date,
            competition_ids=comp_ids,
        )

    def _get_competition_weight(self, competition_id: int) -> float:
        """Get the importance weight for a competition."""
        tier = self._competition_tiers.get(competition_id, CompetitionTier.MEDIUM)
        return tier.value
