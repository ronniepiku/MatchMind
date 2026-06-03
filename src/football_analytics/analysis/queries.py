"""Parameterised analytical query library.

A curated collection of complex, production-grade SQL queries for ad-hoc
football analysis. Each query is parameterised to prevent injection and
designed to answer the kinds of questions coaches and analysts ask daily.

Categories:
- Pressing & Transitions
- Build-Up & Possession
- Chance Creation
- Defensive Shape
- Set Pieces
- Player Scouting
- Head-to-Head
- Form & Momentum

Usage:
    library = AnalyticalQueryLibrary(engine)
    available = library.list_queries()
    result = library.execute("pressing_triggers", {"team_id": 1, "season_id": 90})
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)


@dataclass
class QueryParameter:
    """Definition of a query parameter."""

    name: str
    type: str  # "int", "float", "str", "date", "list[int]"
    description: str
    required: bool = True
    default: Any = None


@dataclass
class AnalyticalQuery:
    """A registered analytical query template."""

    query_id: str
    name: str
    description: str
    category: str
    sql: str
    parameters: list[QueryParameter]
    result_columns: list[str] = field(default_factory=list)


class AnalyticalQueryLibrary:
    """Curated parameterised query library for ad-hoc analysis.

    All queries use parameterised SQL (no string interpolation) to prevent
    injection. Only registered queries can be executed.
    """

    def __init__(self, engine: Engine | None = None):
        self._engine = engine or get_engine()
        self._queries: dict[str, AnalyticalQuery] = {}
        self._register_all()

    def list_queries(self, category: str | None = None) -> list[dict[str, Any]]:
        """List available queries with metadata.

        Args:
            category: Optional category filter.

        Returns:
            List of query descriptors.
        """
        queries = self._queries.values()
        if category:
            queries = [q for q in queries if q.category.lower() == category.lower()]

        return [
            {
                "query_id": q.query_id,
                "name": q.name,
                "description": q.description,
                "category": q.category,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                        "default": p.default,
                    }
                    for p in q.parameters
                ],
            }
            for q in queries
        ]

    def get_categories(self) -> list[str]:
        """Get all available query categories."""
        return sorted(set(q.category for q in self._queries.values()))

    def execute(self, query_id: str, parameters: dict[str, Any]) -> pd.DataFrame:
        """Execute a registered query with validated parameters.

        Args:
            query_id: ID of the registered query.
            parameters: Parameter values (validated against schema).

        Returns:
            DataFrame with query results.

        Raises:
            ValueError: If query_id not found or parameters invalid.
        """
        if query_id not in self._queries:
            raise ValueError(
                f"Unknown query '{query_id}'. Use list_queries() to see available queries."
            )

        query = self._queries[query_id]

        # Validate parameters
        validated = self._validate_params(query, parameters)

        # Execute
        logger.info(
            f"Executing query '{query_id}' with params: {list(validated.keys())}"
        )
        with self._engine.connect() as conn:
            df = pd.read_sql(text(query.sql), conn, params=validated)

        return df

    def execute_to_dict(
        self, query_id: str, parameters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Execute query and return as list of dicts (JSON-serialisable)."""
        df = self.execute(query_id, parameters)
        # Convert numpy types to Python native
        return df.where(df.notna(), None).to_dict(orient="records")

    def _validate_params(
        self, query: AnalyticalQuery, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate and coerce parameters."""
        validated = {}
        for p in query.parameters:
            if p.name in params:
                validated[p.name] = params[p.name]
            elif p.required and p.default is None:
                raise ValueError(
                    f"Missing required parameter '{p.name}' for query '{query.query_id}'."
                )
            elif p.default is not None:
                validated[p.name] = p.default

        return validated

    def _register_all(self) -> None:
        """Register all analytical queries."""
        queries = [
            self._pressing_triggers(),
            self._pressing_success_rate(),
            self._progressive_actions_by_zone(),
            self._build_up_patterns(),
            self._possession_sequences(),
            self._chance_creation_profile(),
            self._shot_quality_breakdown(),
            self._defensive_vulnerability_windows(),
            self._defensive_line_height(),
            self._set_piece_effectiveness(),
            self._set_piece_conceded(),
            self._player_comparison_radar(),
            self._player_progression_over_time(),
            self._head_to_head_tactical(),
            self._style_matchup_history(),
            self._form_momentum(),
            self._high_turnover_zones(),
            self._crossing_effectiveness(),
            self._goalkeeper_distribution(),
            self._counter_attack_speed(),
            self._aerial_dominance_map(),
        ]
        for q in queries:
            self._queries[q.query_id] = q

    # ─── Query Definitions ─────────────────────────────────────────────────

    def _pressing_triggers(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="pressing_triggers",
            name="Pressing Triggers & Recovery",
            description="Where and when does a team press, and how often do they win the ball back within 5 seconds?",
            category="Pressing & Transitions",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                WITH press_events AS (
                    SELECT e.match_id, e.minute, e.second,
                           e.location_x, e.location_y,
                           CASE
                               WHEN e.location_x > 80 THEN 'Final Third'
                               WHEN e.location_x > 40 THEN 'Middle Third'
                               ELSE 'Defensive Third'
                           END AS pitch_zone,
                           e.event_id
                    FROM events e
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE e.team_id = :team_id AND m.season_id = :season_id
                        AND e.event_type = 'Pressure'
                ),
                recoveries AS (
                    SELECT e.match_id, e.minute, e.second, e.team_id
                    FROM events e
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE e.team_id = :team_id AND m.season_id = :season_id
                        AND e.event_type = 'Ball Recovery'
                )
                SELECT
                    pe.pitch_zone,
                    COUNT(*) AS total_pressures,
                    COUNT(DISTINCT pe.match_id) AS matches,
                    ROUND(COUNT(*)::numeric / COUNT(DISTINCT pe.match_id), 1) AS pressures_per_match,
                    ROUND(AVG(pe.location_x)::numeric, 1) AS avg_x,
                    ROUND(AVG(pe.location_y)::numeric, 1) AS avg_y,
                    COUNT(r.match_id) FILTER (WHERE r.minute - pe.minute BETWEEN 0 AND 1) AS quick_recoveries,
                    ROUND(
                        COUNT(r.match_id) FILTER (WHERE r.minute - pe.minute BETWEEN 0 AND 1) * 100.0
                        / NULLIF(COUNT(*), 0), 1
                    ) AS recovery_rate_pct
                FROM press_events pe
                LEFT JOIN recoveries r ON pe.match_id = r.match_id
                    AND r.minute BETWEEN pe.minute AND pe.minute + 1
                GROUP BY pe.pitch_zone
                ORDER BY COUNT(*) DESC
            """,
        )

    def _pressing_success_rate(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="pressing_success_rate",
            name="Pressing Success by Match Phase",
            description="How effective is the press in different periods of the match (0-15, 15-30, 30-45, etc.)?",
            category="Pressing & Transitions",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    CASE
                        WHEN e.minute < 15 THEN '0-15'
                        WHEN e.minute < 30 THEN '15-30'
                        WHEN e.minute < 45 THEN '30-45'
                        WHEN e.minute < 60 THEN '45-60'
                        WHEN e.minute < 75 THEN '60-75'
                        ELSE '75-90+'
                    END AS match_phase,
                    COUNT(*) AS pressures,
                    COUNT(*) FILTER (WHERE e.pressure_regain = TRUE) AS successful,
                    ROUND(
                        COUNT(*) FILTER (WHERE e.pressure_regain = TRUE) * 100.0
                        / NULLIF(COUNT(*), 0), 1
                    ) AS success_rate_pct,
                    COUNT(DISTINCT e.match_id) AS matches
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.event_type = 'Pressure'
                GROUP BY 1
                ORDER BY MIN(e.minute)
            """,
        )

    def _progressive_actions_by_zone(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="progressive_actions_by_zone",
            name="Progressive Actions by Pitch Zone",
            description="Progressive passes and carries broken down by starting zone — identifies where a player or team advances the ball most effectively.",
            category="Build-Up & Possession",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
                QueryParameter(
                    "player_id", "int", "Specific player (optional)", required=False
                ),
            ],
            sql="""
                SELECT
                    CASE
                        WHEN e.location_x < 40 THEN 'Defensive Third'
                        WHEN e.location_x < 80 THEN 'Middle Third'
                        ELSE 'Final Third'
                    END AS start_zone,
                    e.event_type AS action_type,
                    COUNT(*) AS total_actions,
                    COUNT(*) FILTER (WHERE
                        (e.event_type = 'Pass' AND e.pass_end_location_x - e.location_x > 10) OR
                        (e.event_type = 'Carry' AND e.carry_progressive = TRUE)
                    ) AS progressive_actions,
                    ROUND(
                        COUNT(*) FILTER (WHERE
                            (e.event_type = 'Pass' AND e.pass_end_location_x - e.location_x > 10) OR
                            (e.event_type = 'Carry' AND e.carry_progressive = TRUE)
                        ) * 100.0 / NULLIF(COUNT(*), 0), 1
                    ) AS progressive_pct,
                    COUNT(DISTINCT e.match_id) AS matches
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.event_type IN ('Pass', 'Carry')
                    AND (:player_id IS NULL OR e.player_id = :player_id)
                GROUP BY 1, 2
                ORDER BY 1, 2
            """,
        )

    def _build_up_patterns(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="build_up_patterns",
            name="Build-Up Route Analysis",
            description="How does the team build from the back — left, right, or central? Tracks pass sequences from defensive third.",
            category="Build-Up & Possession",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    CASE
                        WHEN e.location_y < 27 THEN 'Left Channel'
                        WHEN e.location_y < 53 THEN 'Central'
                        ELSE 'Right Channel'
                    END AS build_up_channel,
                    COUNT(*) AS passes,
                    COUNT(*) FILTER (WHERE e.pass_outcome IS NULL) AS completed,
                    ROUND(
                        COUNT(*) FILTER (WHERE e.pass_outcome IS NULL) * 100.0
                        / NULLIF(COUNT(*), 0), 1
                    ) AS completion_pct,
                    ROUND(AVG(e.pass_end_location_x - e.location_x)::numeric, 1) AS avg_forward_distance,
                    COUNT(*) FILTER (WHERE e.pass_end_location_x > 80) AS entries_to_final_third
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.event_type = 'Pass'
                    AND e.location_x < 40
                GROUP BY 1
                ORDER BY COUNT(*) DESC
            """,
        )

    def _possession_sequences(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="possession_sequences",
            name="Possession Sequence Outcomes",
            description="Classifies possession sequences by length and outcome (shot, turnover, set piece won).",
            category="Build-Up & Possession",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                WITH sequences AS (
                    SELECT e.possession AS possession_id, e.match_id,
                           COUNT(*) AS events_in_sequence,
                           MAX(CASE WHEN e.event_type = 'Shot' THEN 1 ELSE 0 END) AS ends_in_shot,
                           COALESCE(MAX(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0) AS sequence_xg
                    FROM events e
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE e.team_id = :team_id AND m.season_id = :season_id
                        AND e.possession IS NOT NULL
                    GROUP BY e.possession, e.match_id
                )
                SELECT
                    CASE
                        WHEN events_in_sequence <= 3 THEN 'Short (1-3)'
                        WHEN events_in_sequence <= 7 THEN 'Medium (4-7)'
                        WHEN events_in_sequence <= 12 THEN 'Long (8-12)'
                        ELSE 'Extended (13+)'
                    END AS sequence_length,
                    COUNT(*) AS total_sequences,
                    SUM(ends_in_shot) AS shots_created,
                    ROUND(SUM(ends_in_shot) * 100.0 / NULLIF(COUNT(*), 0), 1) AS shot_pct,
                    ROUND(SUM(sequence_xg)::numeric, 2) AS total_xg,
                    ROUND(AVG(sequence_xg) FILTER (WHERE ends_in_shot = 1)::numeric, 3) AS avg_xg_per_shot
                FROM sequences
                GROUP BY 1
                ORDER BY MIN(events_in_sequence)
            """,
        )

    def _chance_creation_profile(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="chance_creation_profile",
            name="Chance Creation by Method",
            description="How are chances being created — open play, set pieces, counter attacks, individual skill?",
            category="Chance Creation",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    COALESCE(e.play_pattern, 'Open Play') AS creation_method,
                    COUNT(*) AS shots,
                    ROUND(SUM(e.xg)::numeric, 2) AS total_xg,
                    ROUND(AVG(e.xg)::numeric, 3) AS avg_xg_per_shot,
                    COUNT(*) FILTER (WHERE e.shot_outcome = 'Goal') AS goals,
                    COUNT(*) FILTER (WHERE e.shot_outcome IN ('Saved', 'On Target')) AS on_target,
                    COUNT(DISTINCT e.match_id) AS matches
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.event_type = 'Shot'
                GROUP BY 1
                ORDER BY SUM(e.xg) DESC
            """,
        )

    def _shot_quality_breakdown(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="shot_quality_breakdown",
            name="Shot Quality by Zone",
            description="Breakdown of shot volume, quality (xG), and conversion by pitch zone.",
            category="Chance Creation",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    CASE
                        WHEN e.location_x > 102 AND ABS(e.location_y - 40) < 10 THEN 'Six-Yard Box'
                        WHEN e.location_x > 96 AND ABS(e.location_y - 40) < 20 THEN 'Penalty Area Central'
                        WHEN e.location_x > 96 THEN 'Penalty Area Wide'
                        ELSE 'Outside Box'
                    END AS shot_zone,
                    COUNT(*) AS shots,
                    ROUND(SUM(e.xg)::numeric, 2) AS total_xg,
                    ROUND(AVG(e.xg)::numeric, 3) AS avg_xg,
                    COUNT(*) FILTER (WHERE e.shot_outcome = 'Goal') AS goals,
                    ROUND(
                        COUNT(*) FILTER (WHERE e.shot_outcome = 'Goal') * 100.0
                        / NULLIF(COUNT(*), 0), 1
                    ) AS conversion_pct
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.event_type = 'Shot'
                GROUP BY 1
                ORDER BY SUM(e.xg) DESC
            """,
        )

    def _defensive_vulnerability_windows(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="defensive_vulnerability_windows",
            name="Defensive Vulnerability by Time Period",
            description="Minutes where the team concedes disproportionate Expected Goals — identifies when the team is most vulnerable.",
            category="Defensive Shape",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    CASE
                        WHEN e.minute < 15 THEN '0-15'
                        WHEN e.minute < 30 THEN '15-30'
                        WHEN e.minute < 45 THEN '30-45'
                        WHEN e.minute < 60 THEN '45-60'
                        WHEN e.minute < 75 THEN '60-75'
                        ELSE '75-90+'
                    END AS time_window,
                    COUNT(*) AS shots_conceded,
                    ROUND(SUM(e.xg)::numeric, 3) AS xg_conceded,
                    ROUND(AVG(e.xg)::numeric, 3) AS avg_xg_per_shot,
                    COUNT(*) FILTER (WHERE e.shot_outcome = 'Goal') AS goals_conceded,
                    COUNT(DISTINCT e.match_id) AS matches
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id != :team_id AND e.event_type = 'Shot'
                    AND m.season_id = :season_id
                    AND (m.home_team_id = :team_id OR m.away_team_id = :team_id)
                GROUP BY 1
                ORDER BY MIN(e.minute)
            """,
        )

    def _defensive_line_height(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="defensive_line_height",
            name="Defensive Line Height Analysis",
            description="Average defensive action locations — how high or deep does the team defend?",
            category="Defensive Shape",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    e.event_type AS defensive_action,
                    COUNT(*) AS total,
                    ROUND(AVG(e.location_x)::numeric, 1) AS avg_x_position,
                    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY e.location_x)::numeric, 1) AS p25_x,
                    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY e.location_x)::numeric, 1) AS p75_x,
                    ROUND(STDDEV(e.location_x)::numeric, 1) AS std_x,
                    COUNT(DISTINCT e.match_id) AS matches
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.event_type IN ('Pressure', 'Duel', 'Interception', 'Block')
                GROUP BY 1
                ORDER BY AVG(e.location_x) DESC
            """,
        )

    def _set_piece_effectiveness(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="set_piece_effectiveness",
            name="Set-Piece Effectiveness (Attacking)",
            description="Breakdown of set-piece outcomes — corners, free kicks, throw-ins. Goals and xG per routine.",
            category="Set Pieces",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    e.play_pattern AS set_piece_type,
                    COUNT(*) AS shots,
                    ROUND(SUM(e.xg)::numeric, 2) AS total_xg,
                    COUNT(*) FILTER (WHERE e.shot_outcome = 'Goal') AS goals,
                    COUNT(DISTINCT e.match_id) AS matches,
                    ROUND(SUM(e.xg)::numeric / NULLIF(COUNT(DISTINCT e.match_id), 0), 3) AS xg_per_match
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.event_type = 'Shot'
                    AND e.play_pattern IN ('From Corner', 'From Free Kick', 'From Throw In')
                GROUP BY 1
                ORDER BY SUM(e.xg) DESC
            """,
        )

    def _set_piece_conceded(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="set_piece_conceded",
            name="Set-Piece Vulnerability (Defensive)",
            description="Set-piece xG conceded — where is the team most vulnerable from dead-ball situations?",
            category="Set Pieces",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    e.play_pattern AS set_piece_type,
                    COUNT(*) AS shots_conceded,
                    ROUND(SUM(e.xg)::numeric, 2) AS xg_conceded,
                    COUNT(*) FILTER (WHERE e.shot_outcome = 'Goal') AS goals_conceded,
                    COUNT(DISTINCT e.match_id) AS matches,
                    ROUND(SUM(e.xg)::numeric / NULLIF(COUNT(DISTINCT e.match_id), 0), 3) AS xg_per_match
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id != :team_id AND e.event_type = 'Shot'
                    AND m.season_id = :season_id
                    AND (m.home_team_id = :team_id OR m.away_team_id = :team_id)
                    AND e.play_pattern IN ('From Corner', 'From Free Kick', 'From Throw In')
                GROUP BY 1
                ORDER BY SUM(e.xg) DESC
            """,
        )

    def _player_comparison_radar(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="player_comparison_radar",
            name="Player Per-90 Radar Metrics",
            description="Per-90-minute metrics for a player — suitable for radar chart or comparison.",
            category="Player Scouting",
            parameters=[
                QueryParameter("player_id", "int", "Player to profile"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    p.player_name,
                    COUNT(DISTINCT e.match_id) AS matches,
                    ROUND(COUNT(*) FILTER (WHERE e.event_type = 'Shot' AND e.shot_outcome = 'Goal')
                        * 90.0 / NULLIF(COUNT(DISTINCT e.match_id), 0), 2) AS goals_p90,
                    ROUND(COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0)
                        * 90.0 / NULLIF(COUNT(DISTINCT e.match_id) * 90, 0), 3) AS xg_p90,
                    ROUND(COALESCE(SUM(e.xa) FILTER (WHERE e.event_type = 'Pass'), 0)
                        * 90.0 / NULLIF(COUNT(DISTINCT e.match_id) * 90, 0), 3) AS xa_p90,
                    ROUND(COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_shot_assist = TRUE)
                        * 90.0 / NULLIF(COUNT(DISTINCT e.match_id), 0), 2) AS key_passes_p90,
                    ROUND(COUNT(*) FILTER (WHERE e.event_type = 'Carry' AND e.carry_progressive = TRUE)
                        * 90.0 / NULLIF(COUNT(DISTINCT e.match_id), 0), 2) AS prog_carries_p90,
                    ROUND(COUNT(*) FILTER (WHERE e.event_type = 'Pressure')
                        * 90.0 / NULLIF(COUNT(DISTINCT e.match_id), 0), 2) AS pressures_p90,
                    ROUND(COUNT(*) FILTER (WHERE e.event_type = 'Duel' AND e.duel_type = 'Tackle' AND e.duel_outcome = 'Won')
                        * 90.0 / NULLIF(COUNT(DISTINCT e.match_id), 0), 2) AS tackles_won_p90,
                    ROUND(COUNT(*) FILTER (WHERE e.event_type = 'Interception')
                        * 90.0 / NULLIF(COUNT(DISTINCT e.match_id), 0), 2) AS interceptions_p90,
                    ROUND(
                        COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL) * 100.0
                        / NULLIF(COUNT(*) FILTER (WHERE e.event_type = 'Pass'), 0), 1
                    ) AS pass_accuracy_pct
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                JOIN players p ON e.player_id = p.player_id
                WHERE e.player_id = :player_id AND m.season_id = :season_id
                GROUP BY p.player_name
            """,
        )

    def _player_progression_over_time(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="player_progression_over_time",
            name="Player Match-by-Match Progression",
            description="Rolling match-by-match stats for a player to visualise development trend.",
            category="Player Scouting",
            parameters=[
                QueryParameter("player_id", "int", "Player to track"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    m.match_date,
                    m.match_id,
                    COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0) AS match_xg,
                    COALESCE(SUM(e.xa) FILTER (WHERE e.event_type = 'Pass'), 0) AS match_xa,
                    COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures,
                    COUNT(*) FILTER (WHERE e.event_type = 'Carry' AND e.carry_progressive = TRUE) AS prog_carries,
                    COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS passes_completed,
                    COUNT(*) FILTER (WHERE e.event_type = 'Pass') AS passes_total
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.player_id = :player_id AND m.season_id = :season_id
                GROUP BY m.match_date, m.match_id
                ORDER BY m.match_date ASC
            """,
        )

    def _head_to_head_tactical(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="head_to_head_tactical",
            name="Head-to-Head Tactical Breakdown",
            description="Detailed tactical comparison between two teams across their encounters.",
            category="Head-to-Head",
            parameters=[
                QueryParameter("team_a_id", "int", "First team"),
                QueryParameter("team_b_id", "int", "Second team"),
            ],
            sql="""
                SELECT
                    m.match_id,
                    m.match_date,
                    m.home_score || '-' || m.away_score AS score,
                    COALESCE(SUM(e.xg) FILTER (WHERE e.team_id = :team_a_id AND e.event_type = 'Shot'), 0) AS team_a_xg,
                    COALESCE(SUM(e.xg) FILTER (WHERE e.team_id = :team_b_id AND e.event_type = 'Shot'), 0) AS team_b_xg,
                    COUNT(*) FILTER (WHERE e.team_id = :team_a_id AND e.event_type = 'Pressure') AS team_a_pressures,
                    COUNT(*) FILTER (WHERE e.team_id = :team_b_id AND e.event_type = 'Pressure') AS team_b_pressures,
                    COUNT(*) FILTER (WHERE e.team_id = :team_a_id AND e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS team_a_passes,
                    COUNT(*) FILTER (WHERE e.team_id = :team_b_id AND e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS team_b_passes
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE (m.home_team_id = :team_a_id AND m.away_team_id = :team_b_id)
                   OR (m.home_team_id = :team_b_id AND m.away_team_id = :team_a_id)
                GROUP BY m.match_id, m.match_date, m.home_score, m.away_score
                ORDER BY m.match_date DESC
            """,
        )

    def _style_matchup_history(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="style_matchup_history",
            name="Performance vs Team Styles",
            description="How does the team perform against different opponent styles (high press, low block, possession, direct)?",
            category="Head-to-Head",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                WITH opponent_style AS (
                    SELECT m.match_id,
                        CASE WHEN m.home_team_id = :team_id THEN m.away_team_id ELSE m.home_team_id END AS opp_id,
                        COUNT(*) FILTER (WHERE e.event_type = 'Pressure' AND e.team_id != :team_id) AS opp_pressures,
                        COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.team_id != :team_id) AS opp_passes
                    FROM events e
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE m.season_id = :season_id
                        AND (m.home_team_id = :team_id OR m.away_team_id = :team_id)
                    GROUP BY m.match_id, m.home_team_id, m.away_team_id
                )
                SELECT
                    CASE
                        WHEN os.opp_pressures > 180 THEN 'High Press'
                        WHEN os.opp_passes > 400 THEN 'Possession'
                        WHEN os.opp_pressures < 100 AND os.opp_passes < 300 THEN 'Low Block'
                        ELSE 'Balanced'
                    END AS opponent_style,
                    COUNT(*) AS matches,
                    ROUND(AVG(CASE WHEN m.home_team_id = :team_id THEN m.home_score ELSE m.away_score END)::numeric, 1) AS avg_goals_for,
                    ROUND(AVG(CASE WHEN m.home_team_id = :team_id THEN m.away_score ELSE m.home_score END)::numeric, 1) AS avg_goals_against,
                    SUM(CASE
                        WHEN (m.home_team_id = :team_id AND m.home_score > m.away_score) OR
                             (m.away_team_id = :team_id AND m.away_score > m.home_score) THEN 1 ELSE 0
                    END) AS wins,
                    SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) AS draws
                FROM opponent_style os
                JOIN matches m ON os.match_id = m.match_id
                GROUP BY 1
                ORDER BY COUNT(*) DESC
            """,
        )

    def _form_momentum(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="form_momentum",
            name="Rolling Form & Momentum",
            description="5-match rolling average of key performance metrics to visualise momentum.",
            category="Form & Momentum",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                WITH match_stats AS (
                    SELECT m.match_id, m.match_date,
                        CASE
                            WHEN (m.home_team_id = :team_id AND m.home_score > m.away_score) OR
                                 (m.away_team_id = :team_id AND m.away_score > m.home_score) THEN 3
                            WHEN m.home_score = m.away_score THEN 1
                            ELSE 0
                        END AS points,
                        COALESCE(SUM(e.xg) FILTER (WHERE e.team_id = :team_id AND e.event_type = 'Shot'), 0) AS xg_for,
                        COALESCE(SUM(e.xg) FILTER (WHERE e.team_id != :team_id AND e.event_type = 'Shot'), 0) AS xg_against,
                        COUNT(*) FILTER (WHERE e.team_id = :team_id AND e.event_type = 'Pressure') AS pressures
                    FROM events e
                    JOIN matches m ON e.match_id = m.match_id
                    WHERE m.season_id = :season_id
                        AND (m.home_team_id = :team_id OR m.away_team_id = :team_id)
                    GROUP BY m.match_id, m.match_date, m.home_team_id, m.away_team_id, m.home_score, m.away_score
                )
                SELECT match_date, match_id, points,
                    ROUND(xg_for::numeric, 2) AS xg_for,
                    ROUND(xg_against::numeric, 2) AS xg_against,
                    pressures,
                    ROUND(AVG(points) OVER (ORDER BY match_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)::numeric, 2) AS rolling_ppg,
                    ROUND(AVG(xg_for) OVER (ORDER BY match_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)::numeric, 2) AS rolling_xg_for,
                    ROUND(AVG(xg_against) OVER (ORDER BY match_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)::numeric, 2) AS rolling_xg_against
                FROM match_stats
                ORDER BY match_date ASC
            """,
        )

    def _high_turnover_zones(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="high_turnover_zones",
            name="High Turnover Zones",
            description="Where on the pitch does the team lose possession most frequently?",
            category="Pressing & Transitions",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    CASE
                        WHEN e.location_x < 40 THEN 'Defensive Third'
                        WHEN e.location_x < 80 THEN 'Middle Third'
                        ELSE 'Final Third'
                    END AS zone,
                    CASE
                        WHEN e.location_y < 27 THEN 'Left'
                        WHEN e.location_y < 53 THEN 'Central'
                        ELSE 'Right'
                    END AS channel,
                    COUNT(*) AS turnovers,
                    ROUND(AVG(e.location_x)::numeric, 1) AS avg_x,
                    ROUND(AVG(e.location_y)::numeric, 1) AS avg_y,
                    COUNT(DISTINCT e.match_id) AS matches
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.event_type IN ('Miscontrol', 'Dispossessed')
                GROUP BY 1, 2
                ORDER BY COUNT(*) DESC
            """,
        )

    def _crossing_effectiveness(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="crossing_effectiveness",
            name="Crossing Effectiveness",
            description="Cross completion rates and resulting chances by side and delivery type.",
            category="Chance Creation",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    CASE
                        WHEN e.location_y < 27 THEN 'Left Side'
                        ELSE 'Right Side'
                    END AS delivery_side,
                    COUNT(*) AS crosses_attempted,
                    COUNT(*) FILTER (WHERE e.pass_outcome IS NULL) AS crosses_completed,
                    ROUND(
                        COUNT(*) FILTER (WHERE e.pass_outcome IS NULL) * 100.0
                        / NULLIF(COUNT(*), 0), 1
                    ) AS completion_pct,
                    COUNT(*) FILTER (WHERE e.pass_shot_assist = TRUE) AS led_to_shot,
                    COUNT(*) FILTER (WHERE e.pass_goal_assist = TRUE) AS led_to_goal,
                    COUNT(DISTINCT e.match_id) AS matches
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.event_type = 'Pass' AND e.pass_cross = TRUE
                GROUP BY 1
                ORDER BY COUNT(*) DESC
            """,
        )

    def _goalkeeper_distribution(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="goalkeeper_distribution",
            name="Goalkeeper Distribution Profile",
            description="How does the goalkeeper distribute — short, medium, or long? Success rates and progression.",
            category="Build-Up & Possession",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    CASE
                        WHEN e.pass_length < 20 THEN 'Short (< 20m)'
                        WHEN e.pass_length < 40 THEN 'Medium (20-40m)'
                        ELSE 'Long (40m+)'
                    END AS distribution_type,
                    COUNT(*) AS attempts,
                    COUNT(*) FILTER (WHERE e.pass_outcome IS NULL) AS completed,
                    ROUND(
                        COUNT(*) FILTER (WHERE e.pass_outcome IS NULL) * 100.0
                        / NULLIF(COUNT(*), 0), 1
                    ) AS completion_pct,
                    ROUND(AVG(e.pass_end_location_x - e.location_x)::numeric, 1) AS avg_distance_gained,
                    COUNT(DISTINCT e.match_id) AS matches
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.event_type = 'Pass'
                    AND e.location_x < 25
                    AND e.position = 'Goalkeeper'
                GROUP BY 1
                ORDER BY COUNT(*) DESC
            """,
        )

    def _counter_attack_speed(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="counter_attack_speed",
            name="Counter-Attack Speed & Efficiency",
            description="Analyses counter-attacking sequences — how quickly does the team transition and with what xG output?",
            category="Pressing & Transitions",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    COUNT(*) AS counter_attacks,
                    COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots_from_counters,
                    ROUND(COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0)::numeric, 2) AS counter_xg,
                    COUNT(*) FILTER (WHERE e.event_type = 'Shot' AND e.shot_outcome = 'Goal') AS counter_goals,
                    COUNT(DISTINCT e.match_id) AS matches,
                    ROUND(
                        COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0)::numeric
                        / NULLIF(COUNT(DISTINCT e.match_id), 0), 3
                    ) AS counter_xg_per_match
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.play_pattern = 'From Counter'
            """,
        )

    def _aerial_dominance_map(self) -> AnalyticalQuery:
        return AnalyticalQuery(
            query_id="aerial_dominance_map",
            name="Aerial Duel Dominance by Zone",
            description="Where on the pitch does the team win or lose aerial duels? Identifies aerial strengths and weaknesses.",
            category="Defensive Shape",
            parameters=[
                QueryParameter("team_id", "int", "Team to analyse"),
                QueryParameter("season_id", "int", "Season"),
            ],
            sql="""
                SELECT
                    CASE
                        WHEN e.location_x < 40 THEN 'Defensive Third'
                        WHEN e.location_x < 80 THEN 'Middle Third'
                        ELSE 'Attacking Third'
                    END AS zone,
                    COUNT(*) AS total_aerials,
                    COUNT(*) FILTER (WHERE e.duel_outcome = 'Won') AS won,
                    COUNT(*) FILTER (WHERE e.duel_outcome = 'Lost') AS lost,
                    ROUND(
                        COUNT(*) FILTER (WHERE e.duel_outcome = 'Won') * 100.0
                        / NULLIF(COUNT(*), 0), 1
                    ) AS win_pct,
                    ROUND(AVG(e.location_x)::numeric, 1) AS avg_x,
                    ROUND(AVG(e.location_y)::numeric, 1) AS avg_y,
                    COUNT(DISTINCT e.match_id) AS matches
                FROM events e
                JOIN matches m ON e.match_id = m.match_id
                WHERE e.team_id = :team_id AND m.season_id = :season_id
                    AND e.event_type = 'Duel' AND e.duel_type LIKE '%Aerial%'
                GROUP BY 1
                ORDER BY COUNT(*) DESC
            """,
        )
