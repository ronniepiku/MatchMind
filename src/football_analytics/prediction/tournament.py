"""Tournament simulation engine — format-agnostic competition forecasting.

Simulates entire competitions (leagues, groups+knockout, cups) using the
MatchPredictor for individual match outcomes. Supports any format via
configurable TournamentFormat definitions.

Handles: 48-team World Cup, 20-team league (Premier League), Champions League
groups+knockout, domestic cups (straight knockout), two-leg ties — all through
configuration, not code branches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from football_analytics.prediction.team_rating import TeamRating

logger = logging.getLogger(__name__)


class CompetitionFormat(Enum):
    """Standard competition format types."""

    LEAGUE = "league"  # Round-robin (all play all)
    GROUPS_KNOCKOUT = "groups_knockout"  # Group stage → knockout
    KNOCKOUT = "knockout"  # Straight single-leg knockout
    TWO_LEG_KNOCKOUT = "two_leg_knockout"  # Two-legged knockout ties


@dataclass
class Fixture:
    """A scheduled match within a tournament."""

    fixture_id: str
    team_a_id: int
    team_b_id: int
    team_a_name: str = ""
    team_b_name: str = ""
    stage: str = ""  # e.g., "Group A", "Round of 16", "Final"
    matchday: int = 0
    is_neutral: bool = True


@dataclass
class GroupConfig:
    """Configuration for a group within a groups+knockout tournament."""

    group_name: str
    team_ids: list[int]
    teams_advancing: int = 2  # Top N from each group advance


@dataclass
class TournamentFormat:
    """Defines the structure of a competition.

    Use class methods for common presets, or construct custom formats.
    """

    format_type: CompetitionFormat
    name: str
    # Group stage config (if applicable)
    groups: list[GroupConfig] = field(default_factory=list)
    # How many best 3rd-place teams advance (FIFA WC specific)
    best_third_place_count: int = 0
    # Knockout config
    knockout_rounds: int = 0  # Number of knockout rounds after groups
    has_third_place_match: bool = False
    extra_time: bool = True
    penalties: bool = True
    # League config
    matches_per_pair: int = 2  # Home and away in league
    points_win: int = 3
    points_draw: int = 1

    @classmethod
    def world_cup_2026(cls, groups: list[GroupConfig]) -> TournamentFormat:
        """FIFA World Cup 2026 — 48 teams, 12 groups of 4, top 2 + 8 best 3rd advance to R32."""
        return cls(
            format_type=CompetitionFormat.GROUPS_KNOCKOUT,
            name="FIFA World Cup 2026",
            groups=groups,
            best_third_place_count=8,
            knockout_rounds=5,  # R32, R16, QF, SF, Final
            has_third_place_match=True,
            extra_time=True,
            penalties=True,
        )

    @classmethod
    def premier_league(cls, team_ids: list[int]) -> TournamentFormat:
        """Premier League — 20 teams, double round-robin."""
        return cls(
            format_type=CompetitionFormat.LEAGUE,
            name="Premier League",
            groups=[GroupConfig(group_name="League", team_ids=team_ids, teams_advancing=0)],
            matches_per_pair=2,
        )

    @classmethod
    def champions_league(cls, groups: list[GroupConfig]) -> TournamentFormat:
        """UEFA Champions League — group stage + knockout."""
        return cls(
            format_type=CompetitionFormat.GROUPS_KNOCKOUT,
            name="UEFA Champions League",
            groups=groups,
            best_third_place_count=0,
            knockout_rounds=4,  # R16, QF, SF, Final
            has_third_place_match=False,
            extra_time=True,
            penalties=True,
        )

    @classmethod
    def knockout_cup(cls, team_ids: list[int], name: str = "Cup") -> TournamentFormat:
        """Generic straight knockout tournament."""
        n_rounds = int(np.ceil(np.log2(len(team_ids))))
        return cls(
            format_type=CompetitionFormat.KNOCKOUT,
            name=name,
            groups=[GroupConfig(group_name="Draw", team_ids=team_ids, teams_advancing=0)],
            knockout_rounds=n_rounds,
            extra_time=True,
            penalties=True,
        )


@dataclass
class TeamTournamentResult:
    """Per-team tournament outcome probabilities."""

    team_id: int
    team_name: str
    group_name: str | None = None
    # Group stage
    group_first_prob: float = 0.0
    group_second_prob: float = 0.0
    group_third_prob: float = 0.0
    group_advance_prob: float = 0.0
    # Knockout rounds (cumulative: prob of reaching this round)
    round_of_32_prob: float = 0.0
    round_of_16_prob: float = 0.0
    quarter_final_prob: float = 0.0
    semi_final_prob: float = 0.0
    final_prob: float = 0.0
    winner_prob: float = 0.0
    # League (if applicable)
    expected_points: float = 0.0
    expected_position: float = 0.0
    title_prob: float = 0.0
    top_4_prob: float = 0.0
    relegation_prob: float = 0.0


@dataclass
class TournamentResult:
    """Complete tournament simulation result."""

    tournament_name: str
    format_type: str
    n_simulations: int
    team_results: dict[int, TeamTournamentResult]
    # Key matches: fixtures with highest outcome variance
    pivotal_fixtures: list[dict[str, Any]] = field(default_factory=list)
    # Group stage final standings distribution (if applicable)
    group_standings: dict[str, list[dict]] = field(default_factory=dict)


class TournamentSimulator:
    """Format-agnostic tournament simulation engine.

    Runs N complete tournament simulations, using Poisson match models
    for each fixture, and aggregates outcomes into probabilities.

    Usage:
        simulator = TournamentSimulator(ratings)
        format = TournamentFormat.world_cup_2026(groups=[...])
        result = simulator.simulate(format, n_simulations=50_000)
        print(result.team_results[771].winner_prob)  # Argentina's chances
    """

    def __init__(
        self,
        ratings: dict[int, TeamRating],
        default_xg: float = 1.2,
    ) -> None:
        """Initialise tournament simulator.

        Args:
            ratings: Pre-computed team ratings (from TeamRatingEngine).
            default_xg: Default xG for unrated teams.
        """
        self._ratings = ratings
        self._default_xg = default_xg

    def simulate(
        self,
        tournament_format: TournamentFormat,
        n_simulations: int = 10_000,
        seed: int = 42,
    ) -> TournamentResult:
        """Simulate an entire tournament N times.

        Args:
            tournament_format: Competition structure definition.
            n_simulations: Number of complete tournament simulations.
            seed: Random seed for reproducibility.

        Returns:
            TournamentResult with per-team probabilities.
        """
        rng = np.random.default_rng(seed=seed)

        if tournament_format.format_type == CompetitionFormat.LEAGUE:
            return self._simulate_league(tournament_format, n_simulations, rng)
        elif tournament_format.format_type == CompetitionFormat.GROUPS_KNOCKOUT:
            return self._simulate_groups_knockout(tournament_format, n_simulations, rng)
        elif tournament_format.format_type == CompetitionFormat.KNOCKOUT:
            return self._simulate_knockout_tournament(tournament_format, n_simulations, rng)
        else:
            raise ValueError(f"Unsupported format: {tournament_format.format_type}")

    def _simulate_league(
        self,
        fmt: TournamentFormat,
        n_simulations: int,
        rng: np.random.Generator,
    ) -> TournamentResult:
        """Simulate a league (round-robin) competition."""
        team_ids = fmt.groups[0].team_ids
        n_teams = len(team_ids)

        # Track results across simulations
        points_matrix = np.zeros((n_simulations, n_teams))

        for sim in range(n_simulations):
            points = {tid: 0 for tid in team_ids}
            for i, team_a in enumerate(team_ids):
                for j, team_b in enumerate(team_ids):
                    if i >= j:
                        continue
                    # Each pair plays twice (home/away) in a standard league
                    for leg in range(fmt.matches_per_pair):
                        home = team_a if leg == 0 else team_b
                        away = team_b if leg == 0 else team_a
                        home_goals, away_goals = self._simulate_single_match(home, away, rng, neutral=False)
                        if home_goals > away_goals:
                            points[home] += fmt.points_win
                        elif home_goals == away_goals:
                            points[home] += fmt.points_draw
                            points[away] += fmt.points_draw
                        else:
                            points[away] += fmt.points_win

            for idx, tid in enumerate(team_ids):
                points_matrix[sim, idx] = points[tid]

        # Compute probabilities from simulation results
        team_results = {}
        for idx, tid in enumerate(team_ids):
            team_points = points_matrix[:, idx]
            # Position: 1-indexed rank (1 = top)
            positions = np.zeros(n_simulations)
            for sim in range(n_simulations):
                rank = (points_matrix[sim] > points_matrix[sim, idx]).sum() + 1
                positions[sim] = rank

            team_results[tid] = TeamTournamentResult(
                team_id=tid,
                team_name=self._get_team_name(tid),
                expected_points=round(float(team_points.mean()), 1),
                expected_position=round(float(positions.mean()), 1),
                title_prob=round(float((positions == 1).mean()), 4),
                top_4_prob=round(float((positions <= 4).mean()), 4),
                relegation_prob=round(float((positions >= n_teams - 2).mean()), 4),
            )

        return TournamentResult(
            tournament_name=fmt.name,
            format_type=fmt.format_type.value,
            n_simulations=n_simulations,
            team_results=team_results,
        )

    def _simulate_groups_knockout(
        self,
        fmt: TournamentFormat,
        n_simulations: int,
        rng: np.random.Generator,
    ) -> TournamentResult:
        """Simulate a groups + knockout tournament (World Cup, Champions League)."""
        all_team_ids = [tid for g in fmt.groups for tid in g.team_ids]

        # Counters for probabilities
        group_first = {tid: 0 for tid in all_team_ids}
        group_second = {tid: 0 for tid in all_team_ids}
        group_third = {tid: 0 for tid in all_team_ids}
        advanced = {tid: 0 for tid in all_team_ids}
        reached_round = {r: {tid: 0 for tid in all_team_ids} for r in range(fmt.knockout_rounds + 1)}
        winner_count = {tid: 0 for tid in all_team_ids}

        self._get_knockout_round_names(fmt.knockout_rounds)

        for _sim in range(n_simulations):
            # --- GROUP STAGE ---
            group_qualifiers = []
            third_place_teams: list[tuple[int, int, int]] = []  # (team_id, points, goal_diff)

            for group in fmt.groups:
                standings = self._simulate_group(group, rng)
                # standings: list of (team_id, points, goal_diff) sorted
                if len(standings) >= 1:
                    group_first[standings[0][0]] += 1
                if len(standings) >= 2:
                    group_second[standings[1][0]] += 1
                if len(standings) >= 3:
                    group_third[standings[2][0]] += 1

                # Top N advance
                for i in range(min(group.teams_advancing, len(standings))):
                    group_qualifiers.append(standings[i][0])
                    advanced[standings[i][0]] += 1

                # Track 3rd place for best-third-place rule
                if fmt.best_third_place_count > 0 and len(standings) >= 3:
                    third_place_teams.append(standings[2])

            # Best 3rd place teams
            if fmt.best_third_place_count > 0 and third_place_teams:
                third_place_teams.sort(key=lambda x: (-x[1], -x[2]))
                for i in range(min(fmt.best_third_place_count, len(third_place_teams))):
                    group_qualifiers.append(third_place_teams[i][0])
                    advanced[third_place_teams[i][0]] += 1

            # Mark all qualifiers as reaching round 0 (first knockout round)
            for tid in group_qualifiers:
                reached_round[0][tid] += 1

            # --- KNOCKOUT STAGE ---
            # Shuffle qualifiers for bracket (simplified: random draw each sim)
            bracket = list(group_qualifiers)
            rng.shuffle(bracket)

            for knockout_round in range(fmt.knockout_rounds):
                if len(bracket) < 2:
                    break

                next_bracket = []
                for i in range(0, len(bracket) - 1, 2):
                    team_a = bracket[i]
                    team_b = bracket[i + 1]
                    winner = self._simulate_knockout_match(team_a, team_b, rng)
                    next_bracket.append(winner)
                    # Winner reaches next round
                    if knockout_round + 1 < fmt.knockout_rounds:
                        reached_round[knockout_round + 1][winner] += 1

                # Handle odd team (bye)
                if len(bracket) % 2 == 1:
                    bye_team = bracket[-1]
                    next_bracket.append(bye_team)
                    if knockout_round + 1 < fmt.knockout_rounds:
                        reached_round[knockout_round + 1][bye_team] += 1

                bracket = next_bracket

            # Tournament winner
            if bracket:
                winner_count[bracket[0]] += 1

        # Build results
        team_results = {}
        for tid in all_team_ids:
            # Determine group
            group_name = None
            for g in fmt.groups:
                if tid in g.team_ids:
                    group_name = g.group_name
                    break

            result = TeamTournamentResult(
                team_id=tid,
                team_name=self._get_team_name(tid),
                group_name=group_name,
                group_first_prob=round(group_first[tid] / n_simulations, 4),
                group_second_prob=round(group_second[tid] / n_simulations, 4),
                group_third_prob=round(group_third[tid] / n_simulations, 4),
                group_advance_prob=round(advanced[tid] / n_simulations, 4),
                winner_prob=round(winner_count[tid] / n_simulations, 4),
            )

            # Assign knockout round probabilities dynamically
            if fmt.knockout_rounds >= 1:
                result.round_of_32_prob = round(reached_round[0][tid] / n_simulations, 4)
            if fmt.knockout_rounds >= 2:
                result.round_of_16_prob = round(reached_round[1][tid] / n_simulations, 4)
            if fmt.knockout_rounds >= 3:
                result.quarter_final_prob = round(reached_round[2][tid] / n_simulations, 4)
            if fmt.knockout_rounds >= 4:
                result.semi_final_prob = round(reached_round[3][tid] / n_simulations, 4)
            if fmt.knockout_rounds >= 5:
                result.final_prob = round(reached_round[4][tid] / n_simulations, 4)

            team_results[tid] = result

        return TournamentResult(
            tournament_name=fmt.name,
            format_type=fmt.format_type.value,
            n_simulations=n_simulations,
            team_results=team_results,
        )

    def _simulate_knockout_tournament(
        self,
        fmt: TournamentFormat,
        n_simulations: int,
        rng: np.random.Generator,
    ) -> TournamentResult:
        """Simulate a straight knockout tournament (FA Cup style)."""
        team_ids = fmt.groups[0].team_ids
        winner_count = {tid: 0 for tid in team_ids}
        round_reached = {r: {tid: 0 for tid in team_ids} for r in range(fmt.knockout_rounds)}

        for _sim in range(n_simulations):
            bracket = list(team_ids)
            rng.shuffle(bracket)

            for round_idx in range(fmt.knockout_rounds):
                for tid in bracket:
                    round_reached[round_idx][tid] += 1

                next_bracket = []
                for i in range(0, len(bracket) - 1, 2):
                    winner = self._simulate_knockout_match(bracket[i], bracket[i + 1], rng)
                    next_bracket.append(winner)
                if len(bracket) % 2 == 1:
                    next_bracket.append(bracket[-1])
                bracket = next_bracket

            if bracket:
                winner_count[bracket[0]] += 1

        team_results = {}
        for tid in team_ids:
            team_results[tid] = TeamTournamentResult(
                team_id=tid,
                team_name=self._get_team_name(tid),
                winner_prob=round(winner_count[tid] / n_simulations, 4),
                quarter_final_prob=(
                    round(
                        round_reached.get(fmt.knockout_rounds - 3, {}).get(tid, 0) / n_simulations,
                        4,
                    )
                    if fmt.knockout_rounds >= 3
                    else 0.0
                ),
                semi_final_prob=(
                    round(
                        round_reached.get(fmt.knockout_rounds - 2, {}).get(tid, 0) / n_simulations,
                        4,
                    )
                    if fmt.knockout_rounds >= 2
                    else 0.0
                ),
                final_prob=round(
                    round_reached.get(fmt.knockout_rounds - 1, {}).get(tid, 0) / n_simulations,
                    4,
                ),
            )

        return TournamentResult(
            tournament_name=fmt.name,
            format_type=fmt.format_type.value,
            n_simulations=n_simulations,
            team_results=team_results,
        )

    def _simulate_group(self, group: GroupConfig, rng: np.random.Generator) -> list[tuple[int, int, int]]:
        """Simulate a single group (round-robin within group).

        Returns: Sorted list of (team_id, points, goal_difference).
        """
        points = {tid: 0 for tid in group.team_ids}
        goal_diff = {tid: 0 for tid in group.team_ids}

        # All teams play each other once
        for i, team_a in enumerate(group.team_ids):
            for j, team_b in enumerate(group.team_ids):
                if i >= j:
                    continue
                goals_a, goals_b = self._simulate_single_match(team_a, team_b, rng, neutral=True)
                goal_diff[team_a] += goals_a - goals_b
                goal_diff[team_b] += goals_b - goals_a

                if goals_a > goals_b:
                    points[team_a] += 3
                elif goals_a == goals_b:
                    points[team_a] += 1
                    points[team_b] += 1
                else:
                    points[team_b] += 3

        # Sort: points desc, then goal difference desc
        standings = [(tid, points[tid], goal_diff[tid]) for tid in group.team_ids]
        standings.sort(key=lambda x: (-x[1], -x[2]))
        return standings

    def _simulate_knockout_match(self, team_a: int, team_b: int, rng: np.random.Generator) -> int:
        """Simulate a knockout match (must produce a winner)."""
        goals_a, goals_b = self._simulate_single_match(team_a, team_b, rng, neutral=True)
        if goals_a > goals_b:
            return team_a
        elif goals_b > goals_a:
            return team_b
        else:
            # Extra time: simulate with reduced xG (30 min ≈ 1/3 of match)
            xg_a, xg_b = self._get_match_xg(team_a, team_b, neutral=True)
            et_goals_a = rng.poisson(max(0.1, xg_a * 0.33))
            et_goals_b = rng.poisson(max(0.1, xg_b * 0.33))
            if et_goals_a > et_goals_b:
                return team_a
            elif et_goals_b > et_goals_a:
                return team_b
            else:
                # Penalties: 50/50 with slight bias to stronger team
                overall_a = self._get_overall_rating(team_a)
                overall_b = self._get_overall_rating(team_b)
                total = overall_a + overall_b
                pen_prob_a = (overall_a / total) if total > 0 else 0.5
                # Regress toward 50/50 (penalties are high-variance)
                pen_prob_a = 0.5 + (pen_prob_a - 0.5) * 0.2
                return team_a if rng.random() < pen_prob_a else team_b

    def _simulate_single_match(
        self,
        team_a: int,
        team_b: int,
        rng: np.random.Generator,
        neutral: bool = True,
    ) -> tuple[int, int]:
        """Simulate a single match, returning (goals_a, goals_b)."""
        xg_a, xg_b = self._get_match_xg(team_a, team_b, neutral=neutral)

        # Add per-match variance
        lambda_a = max(0.1, rng.normal(xg_a, 0.15 * xg_a))
        lambda_b = max(0.1, rng.normal(xg_b, 0.15 * xg_b))

        goals_a = int(rng.poisson(lambda_a))
        goals_b = int(rng.poisson(lambda_b))
        return goals_a, goals_b

    def _get_match_xg(self, team_a: int, team_b: int, neutral: bool = True) -> tuple[float, float]:
        """Derive expected xG for a matchup based on ratings."""
        rating_a = self._ratings.get(team_a)
        rating_b = self._ratings.get(team_b)

        avg_defense = 1.2  # League average

        if rating_a and rating_b:
            xg_a = rating_a.offensive_strength * (avg_defense / max(rating_b.defensive_strength, 0.3))
            xg_b = rating_b.offensive_strength * (avg_defense / max(rating_a.defensive_strength, 0.3))
        elif rating_a:
            xg_a = rating_a.offensive_strength
            xg_b = self._default_xg
        elif rating_b:
            xg_a = self._default_xg
            xg_b = rating_b.offensive_strength
        else:
            xg_a = self._default_xg
            xg_b = self._default_xg

        # Home advantage (only if not neutral)
        if not neutral:
            xg_a *= 1.1

        # Clamp
        xg_a = max(0.3, min(xg_a, 4.0))
        xg_b = max(0.3, min(xg_b, 4.0))

        return xg_a, xg_b

    def _get_overall_rating(self, team_id: int) -> float:
        """Get team's overall rating (for tiebreakers)."""
        rating = self._ratings.get(team_id)
        if rating:
            return max(0.1, rating.overall_rating + 1.5)  # Shift to positive
        return 1.0

    def _get_team_name(self, team_id: int) -> str:
        """Get team name from ratings."""
        rating = self._ratings.get(team_id)
        return rating.team_name if rating else f"Team {team_id}"

    def _get_knockout_round_names(self, n_rounds: int) -> list[str]:
        """Generate round names for knockout stage."""
        names = {
            1: ["Final"],
            2: ["Semi-Final", "Final"],
            3: ["Quarter-Final", "Semi-Final", "Final"],
            4: ["Round of 16", "Quarter-Final", "Semi-Final", "Final"],
            5: ["Round of 32", "Round of 16", "Quarter-Final", "Semi-Final", "Final"],
        }
        return names.get(n_rounds, [f"Round {i + 1}" for i in range(n_rounds)])
