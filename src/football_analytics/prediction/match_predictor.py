"""Match prediction service — competition-agnostic outcome forecasting.

Takes any two teams (with or without pre-computed ratings), derives expected
performance metrics, and runs Monte Carlo simulation to produce outcome
probabilities with confidence levels and explanatory factors.

Works identically for Premier League, Champions League, World Cup, or any
competition — venue type and competition context are first-class parameters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.analysis.simulation import simulate_match
from football_analytics.db import get_engine
from football_analytics.prediction.team_rating import TeamRating, TeamRatingEngine

logger = logging.getLogger(__name__)


class VenueType(Enum):
    """Match venue context — affects home advantage factor."""

    HOME = "home"
    AWAY = "away"
    NEUTRAL = "neutral"


# Home advantage multipliers by venue type
_VENUE_FACTORS = {
    VenueType.HOME: 1.10,  # ~10% xG boost for home team
    VenueType.AWAY: 1.0,  # No adjustment (away is default perspective)
    VenueType.NEUTRAL: 1.0,  # No advantage at neutral venue
}


class ConfidenceLevel(Enum):
    """Prediction confidence based on data availability."""

    HIGH = "high"  # Both teams have 15+ matches of data
    MEDIUM = "medium"  # Both teams have 5+ matches
    LOW = "low"  # One or both teams have <5 matches
    INSUFFICIENT = "insufficient"  # Cannot produce reliable prediction


@dataclass
class HeadToHead:
    """Historical head-to-head record between two teams."""

    matches_played: int
    team_a_wins: int
    draws: int
    team_b_wins: int
    team_a_avg_xg: float
    team_b_avg_xg: float
    last_meeting: date | None = None


@dataclass
class PredictionFactor:
    """An explanatory factor contributing to the prediction."""

    dimension: str  # e.g., "offensive_superiority", "home_advantage"
    description: str  # Human-readable explanation
    impact: float  # Signed impact magnitude (-1 to +1 scale, + favours team_a)


@dataclass
class MatchPrediction:
    """Complete match outcome prediction with context."""

    # Teams
    team_a_id: int
    team_a_name: str
    team_b_id: int
    team_b_name: str

    # Core prediction
    team_a_win_prob: float
    draw_prob: float
    team_b_win_prob: float
    most_likely_score: tuple[int, int]
    scoreline_probabilities: dict[tuple[int, int], float]

    # Derived markets
    over_1_5_prob: float
    over_2_5_prob: float
    over_3_5_prob: float
    btts_prob: float

    # Model inputs (transparency)
    team_a_expected_xg: float
    team_b_expected_xg: float

    # Context
    venue_type: str
    competition_id: int | None
    confidence: str  # ConfidenceLevel value
    n_simulations: int

    # Explanatory
    key_factors: list[PredictionFactor] = field(default_factory=list)
    head_to_head: HeadToHead | None = None

    # Metadata
    model_version: str = "v1.0"
    computed_at: date = field(default_factory=date.today)


class MatchPredictor:
    """Competition-agnostic match outcome prediction service.

    Combines team ratings, head-to-head history, and venue context
    to produce probabilistic match forecasts.

    Usage:
        predictor = MatchPredictor(db_engine)
        prediction = predictor.predict(
            team_a_id=771,  # Argentina
            team_b_id=773,  # France
            competition_id=43,  # World Cup
            venue_type=VenueType.NEUTRAL,
        )
        print(f"Argentina win: {prediction.team_a_win_prob:.1%}")
    """

    def __init__(
        self,
        engine: Engine | None = None,
        rating_engine: TeamRatingEngine | None = None,
        n_simulations: int = 10_000,
    ) -> None:
        self._engine = engine or get_engine()
        self._rating_engine = rating_engine or TeamRatingEngine(engine=self._engine)
        self._n_simulations = n_simulations
        self._ratings_cache: dict[int, TeamRating] | None = None

    def predict(
        self,
        team_a_id: int,
        team_b_id: int,
        competition_id: int | None = None,
        venue_type: VenueType = VenueType.NEUTRAL,
        ratings: dict[int, TeamRating] | None = None,
        n_simulations: int | None = None,
    ) -> MatchPrediction:
        """Predict match outcome for any two teams.

        Args:
            team_a_id: First team (conceptually "home" if venue is HOME).
            team_b_id: Second team.
            competition_id: Optional competition context for rating lookup.
            venue_type: Venue context (HOME, AWAY, NEUTRAL).
            ratings: Pre-computed ratings dict. If None, computes fresh.
            n_simulations: Override default simulation count.

        Returns:
            MatchPrediction with probabilities, confidence, and explanatory factors.
        """
        n_sims = n_simulations or self._n_simulations

        # Get or compute ratings
        if ratings is None:
            ratings = self._get_or_compute_ratings(competition_id)

        rating_a = ratings.get(team_a_id)
        rating_b = ratings.get(team_b_id)

        # Determine confidence
        confidence = self._assess_confidence(rating_a, rating_b)

        # Derive expected xG for each team
        xg_a, xg_b = self._derive_expected_xg(rating_a, rating_b, venue_type)

        # Get head-to-head history
        h2h = self._get_head_to_head(team_a_id, team_b_id)

        # Apply head-to-head adjustment (subtle: max ±5% influence)
        xg_a, xg_b = self._apply_h2h_adjustment(xg_a, xg_b, h2h)

        # Run Monte Carlo simulation
        home_advantage = _VENUE_FACTORS[venue_type]
        sim_result = simulate_match(
            home_xg=xg_a,
            away_xg=xg_b,
            home_team=self._get_team_name(team_a_id, rating_a),
            away_team=self._get_team_name(team_b_id, rating_b),
            n_simulations=n_sims,
            home_advantage_factor=home_advantage,
        )

        # Build explanatory factors
        factors = self._build_factors(rating_a, rating_b, venue_type, h2h)

        return MatchPrediction(
            team_a_id=team_a_id,
            team_a_name=sim_result.home_team,
            team_b_id=team_b_id,
            team_b_name=sim_result.away_team,
            team_a_win_prob=sim_result.home_win_prob,
            draw_prob=sim_result.draw_prob,
            team_b_win_prob=sim_result.away_win_prob,
            most_likely_score=sim_result.most_likely_score,
            scoreline_probabilities=sim_result.scoreline_probabilities,
            over_1_5_prob=sim_result.over_1_5_prob,
            over_2_5_prob=sim_result.over_2_5_prob,
            over_3_5_prob=sim_result.over_3_5_prob,
            btts_prob=sim_result.btts_prob,
            team_a_expected_xg=round(xg_a, 3),
            team_b_expected_xg=round(xg_b, 3),
            venue_type=venue_type.value,
            competition_id=competition_id,
            confidence=confidence.value,
            n_simulations=n_sims,
            key_factors=factors,
            head_to_head=h2h,
        )

    def predict_batch(
        self,
        fixtures: list[dict],
        competition_id: int | None = None,
        ratings: dict[int, TeamRating] | None = None,
    ) -> list[MatchPrediction]:
        """Predict multiple matches efficiently (shared ratings computation).

        Args:
            fixtures: List of dicts with keys: team_a_id, team_b_id, venue_type.
            competition_id: Optional competition context.
            ratings: Pre-computed ratings. If None, computed once and reused.

        Returns:
            List of MatchPrediction in same order as fixtures.
        """
        if ratings is None:
            ratings = self._get_or_compute_ratings(competition_id)

        predictions = []
        for fixture in fixtures:
            venue = fixture.get("venue_type", VenueType.NEUTRAL)
            if isinstance(venue, str):
                venue = VenueType(venue)
            pred = self.predict(
                team_a_id=fixture["team_a_id"],
                team_b_id=fixture["team_b_id"],
                competition_id=competition_id,
                venue_type=venue,
                ratings=ratings,
            )
            predictions.append(pred)

        return predictions

    def _get_or_compute_ratings(self, competition_id: int | None) -> dict[int, TeamRating]:
        """Get cached ratings or compute fresh ones."""
        if self._ratings_cache is not None:
            return self._ratings_cache

        comp_ids = [competition_id] if competition_id else None
        self._ratings_cache = self._rating_engine.compute_ratings(competition_ids=comp_ids)
        return self._ratings_cache

    def _derive_expected_xg(
        self,
        rating_a: TeamRating | None,
        rating_b: TeamRating | None,
        venue_type: VenueType,
    ) -> tuple[float, float]:
        """Derive expected xG for each team based on ratings matchup.

        Uses the interaction between team A's attack strength and team B's
        defensive strength (and vice versa).
        """
        # Fallback xG for unrated teams (league average)
        default_xg = 1.2

        if rating_a is None and rating_b is None:
            return default_xg, default_xg

        # Team A expected xG: their offensive strength adjusted by opponent defense
        if rating_a and rating_b:
            # Interaction model: attacker strength * (avg_defense / opponent_defense)
            avg_defense = 1.2  # League average xG conceded
            xg_a = rating_a.offensive_strength * (avg_defense / max(rating_b.defensive_strength, 0.3))
            xg_b = rating_b.offensive_strength * (avg_defense / max(rating_a.defensive_strength, 0.3))
        elif rating_a:
            xg_a = rating_a.offensive_strength
            xg_b = default_xg
        else:
            xg_a = default_xg
            xg_b = rating_b.offensive_strength  # type: ignore[union-attr]

        # Clamp to reasonable range
        xg_a = max(0.3, min(xg_a, 4.0))
        xg_b = max(0.3, min(xg_b, 4.0))

        return xg_a, xg_b

    def _apply_h2h_adjustment(
        self,
        xg_a: float,
        xg_b: float,
        h2h: HeadToHead | None,
    ) -> tuple[float, float]:
        """Subtle adjustment based on head-to-head history.

        Maximum ±5% influence — H2H is informative but shouldn't dominate.
        """
        if h2h is None or h2h.matches_played < 2:
            return xg_a, xg_b

        # Compare H2H xG averages to current expectation
        if h2h.team_a_avg_xg > 0 and h2h.team_b_avg_xg > 0:
            h2h_ratio_a = h2h.team_a_avg_xg / xg_a if xg_a > 0 else 1.0
            h2h_ratio_b = h2h.team_b_avg_xg / xg_b if xg_b > 0 else 1.0

            # Blend: 95% model + 5% H2H historical
            blend = 0.05
            adj_a = xg_a * (1 - blend + blend * min(max(h2h_ratio_a, 0.8), 1.2))
            adj_b = xg_b * (1 - blend + blend * min(max(h2h_ratio_b, 0.8), 1.2))
            return adj_a, adj_b

        return xg_a, xg_b

    def _get_head_to_head(self, team_a_id: int, team_b_id: int) -> HeadToHead | None:
        """Fetch head-to-head record from database."""
        query = text("""
            SELECT
                m.match_id,
                m.match_date,
                m.home_team_id,
                m.away_team_id,
                m.home_score,
                m.away_score,
                COALESCE(SUM(e.xg) FILTER (WHERE e.team_id = :team_a AND e.event_type = 'Shot'), 0) AS team_a_xg,
                COALESCE(SUM(e.xg) FILTER (WHERE e.team_id = :team_b AND e.event_type = 'Shot'), 0) AS team_b_xg
            FROM matches m
            LEFT JOIN events e ON e.match_id = m.match_id
            WHERE (m.home_team_id = :team_a AND m.away_team_id = :team_b)
               OR (m.home_team_id = :team_b AND m.away_team_id = :team_a)
            GROUP BY m.match_id, m.match_date, m.home_team_id, m.away_team_id, m.home_score, m.away_score
            ORDER BY m.match_date DESC
        """)

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(query, conn, params={"team_a": team_a_id, "team_b": team_b_id})
        except Exception:
            return None

        if df.empty:
            return None

        # Compute H2H stats
        a_wins = 0
        b_wins = 0
        draws = 0
        for _, row in df.iterrows():
            if row["home_team_id"] == team_a_id:
                if row["home_score"] > row["away_score"]:
                    a_wins += 1
                elif row["home_score"] < row["away_score"]:
                    b_wins += 1
                else:
                    draws += 1
            else:
                if row["away_score"] > row["home_score"]:
                    a_wins += 1
                elif row["away_score"] < row["home_score"]:
                    b_wins += 1
                else:
                    draws += 1

        return HeadToHead(
            matches_played=len(df),
            team_a_wins=a_wins,
            draws=draws,
            team_b_wins=b_wins,
            team_a_avg_xg=round(float(df["team_a_xg"].mean()), 3),
            team_b_avg_xg=round(float(df["team_b_xg"].mean()), 3),
            last_meeting=pd.to_datetime(df["match_date"].iloc[0]).date(),
        )

    def _assess_confidence(self, rating_a: TeamRating | None, rating_b: TeamRating | None) -> ConfidenceLevel:
        """Assess prediction confidence based on data availability."""
        if rating_a is None or rating_b is None:
            return ConfidenceLevel.LOW if (rating_a or rating_b) else ConfidenceLevel.INSUFFICIENT

        if rating_a.confidence == "high" and rating_b.confidence == "high":
            return ConfidenceLevel.HIGH
        elif rating_a.confidence == "low" or rating_b.confidence == "low":
            return ConfidenceLevel.LOW
        return ConfidenceLevel.MEDIUM

    def _build_factors(
        self,
        rating_a: TeamRating | None,
        rating_b: TeamRating | None,
        venue_type: VenueType,
        h2h: HeadToHead | None,
    ) -> list[PredictionFactor]:
        """Generate human-readable explanatory factors."""
        factors = []

        if rating_a and rating_b:
            # Offensive comparison
            off_diff = rating_a.offensive_strength - rating_b.offensive_strength
            if abs(off_diff) > 0.2:
                stronger = rating_a.team_name if off_diff > 0 else rating_b.team_name
                factors.append(
                    PredictionFactor(
                        dimension="offensive_quality",
                        description=f"{stronger} creates significantly more expected goals per match",
                        impact=round(off_diff / 2, 3),
                    )
                )

            # Defensive comparison
            def_diff = rating_b.defensive_strength - rating_a.defensive_strength
            if abs(def_diff) > 0.2:
                stronger = rating_a.team_name if def_diff > 0 else rating_b.team_name
                factors.append(
                    PredictionFactor(
                        dimension="defensive_solidity",
                        description=f"{stronger} concedes fewer expected goals per match",
                        impact=round(def_diff / 2, 3),
                    )
                )

            # Pressing
            press_diff = rating_a.pressing_intensity - rating_b.pressing_intensity
            if abs(press_diff) > 5:
                aggressive = rating_a.team_name if press_diff > 0 else rating_b.team_name
                factors.append(
                    PredictionFactor(
                        dimension="pressing_intensity",
                        description=f"{aggressive} applies significantly more pressure",
                        impact=round(press_diff / 50, 3),
                    )
                )

        # Venue
        if venue_type == VenueType.HOME:
            factors.append(
                PredictionFactor(
                    dimension="home_advantage",
                    description="Home venue provides a statistical advantage",
                    impact=0.1,
                )
            )

        # Head-to-head
        if h2h and h2h.matches_played >= 3 and h2h.team_a_wins > h2h.team_b_wins * 1.5:
            factors.append(
                PredictionFactor(
                    dimension="head_to_head",
                    description=f"Strong historical record in this fixture ({h2h.team_a_wins}W-{h2h.draws}D-{h2h.team_b_wins}L)",
                    impact=0.05,
                )
            )

        return factors

    def _get_team_name(self, team_id: int, rating: TeamRating | None) -> str:
        """Get team name from rating or database."""
        if rating:
            return rating.team_name

        query = text("SELECT team_name FROM teams WHERE team_id = :tid")
        try:
            with self._engine.connect() as conn:
                result = conn.execute(query, {"tid": team_id}).fetchone()
                return result[0] if result else f"Team {team_id}"
        except Exception:
            return f"Team {team_id}"
