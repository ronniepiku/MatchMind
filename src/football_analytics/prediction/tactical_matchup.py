"""Tactical matchup analysis — comparative team profile assessment.

Analyses how two teams' tactical profiles interact to identify advantages,
vulnerabilities, and key battles. Competition-agnostic: works for any
fixture where both teams have event data.

Output is structured for both coaching staff consumption (narratives)
and dashboard display (scores/charts).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)


@dataclass
class TacticalDimension:
    """A single tactical comparison dimension."""

    name: str
    team_a_score: float  # Raw metric for team A
    team_b_score: float  # Raw metric for team B
    advantage: float  # -1 to +1 scale (+ favours team_a)
    description: str  # Human-readable interpretation


@dataclass
class KeyBattle:
    """An identified player-level or unit-level tactical battle."""

    area: str  # e.g., "Left flank", "Aerial duels", "Central midfield"
    team_a_factor: str  # What team A brings
    team_b_factor: str  # What team B brings
    significance: str  # "high", "medium", "low"
    narrative: str  # Coaching-friendly description


@dataclass
class TacticalMatchup:
    """Complete tactical matchup analysis between two teams."""

    team_a_id: int
    team_a_name: str
    team_b_id: int
    team_b_name: str

    # Dimension-level comparison
    dimensions: list[TacticalDimension]

    # Key battles
    key_battles: list[KeyBattle]

    # Summary
    overall_advantage: float  # -1 to +1 (+ favours team_a)
    tactical_narrative: str  # Executive summary of matchup
    recommendations: list[str]  # Tactical suggestions

    # Metadata
    matches_analysed_a: int = 0
    matches_analysed_b: int = 0
    competition_ids: list[int] = field(default_factory=list)


def analyse_matchup(
    team_a_id: int,
    team_b_id: int,
    competition_id: int | None = None,
    season_id: int | None = None,
    engine: Engine | None = None,
) -> TacticalMatchup:
    """Analyse tactical matchup between two teams.

    Compares team profiles across multiple tactical dimensions and identifies
    key battles and strategic advantages.

    Args:
        team_a_id: First team (conceptually "our team" for recommendations).
        team_b_id: Second team (the opponent).
        competition_id: Filter analysis to specific competition.
        season_id: Filter to specific season.
        engine: SQLAlchemy engine. Uses default if None.

    Returns:
        TacticalMatchup with dimensions, battles, and narrative.
    """
    engine = engine or get_engine()

    profile_a = _build_tactical_profile(engine, team_a_id, competition_id, season_id)
    profile_b = _build_tactical_profile(engine, team_b_id, competition_id, season_id)

    if profile_a is None or profile_b is None:
        missing = team_a_id if profile_a is None else team_b_id
        logger.warning(f"Insufficient data for team {missing}")
        return TacticalMatchup(
            team_a_id=team_a_id,
            team_a_name=profile_a["team_name"] if profile_a else f"Team {team_a_id}",
            team_b_id=team_b_id,
            team_b_name=profile_b["team_name"] if profile_b else f"Team {team_b_id}",
            dimensions=[],
            key_battles=[],
            overall_advantage=0.0,
            tactical_narrative="Insufficient data for tactical analysis.",
            recommendations=[],
        )

    # Build dimensional comparison
    dimensions = _compare_dimensions(profile_a, profile_b)

    # Identify key battles
    key_battles = _identify_key_battles(profile_a, profile_b)

    # Compute overall advantage
    overall = _compute_overall_advantage(dimensions)

    # Generate narrative and recommendations
    narrative = _generate_narrative(profile_a, profile_b, dimensions)
    recommendations = _generate_recommendations(profile_a, profile_b, dimensions)

    return TacticalMatchup(
        team_a_id=team_a_id,
        team_a_name=profile_a["team_name"],
        team_b_id=team_b_id,
        team_b_name=profile_b["team_name"],
        dimensions=dimensions,
        key_battles=key_battles,
        overall_advantage=overall,
        tactical_narrative=narrative,
        recommendations=recommendations,
        matches_analysed_a=profile_a["matches"],
        matches_analysed_b=profile_b["matches"],
    )


def _build_tactical_profile(
    engine: Engine,
    team_id: int,
    competition_id: int | None,
    season_id: int | None,
) -> dict[str, Any] | None:
    """Build comprehensive tactical profile for a team."""
    filters = ["e.team_id = :team_id"]
    params: dict[str, Any] = {"team_id": team_id}

    if competition_id:
        filters.append("m.competition_id = :comp_id")
        params["comp_id"] = competition_id
    if season_id:
        filters.append("m.season_id = :season_id")
        params["season_id"] = season_id

    where = " AND ".join(filters)

    query = text(f"""
        WITH team_events AS (
            SELECT e.*, m.match_date, m.home_team_id, m.away_team_id
            FROM events e
            JOIN matches m ON e.match_id = m.match_id
            WHERE {where}
        ),
        match_count AS (
            SELECT COUNT(DISTINCT match_id) AS matches FROM team_events
        )
        SELECT
            t.team_name,
            mc.matches,
            -- Offensive
            COALESCE(SUM(te.xg) FILTER (WHERE te.event_type = 'Shot'), 0) /
                NULLIF((SELECT matches FROM match_count), 0) AS xg_per_match,
            COUNT(*) FILTER (WHERE te.event_type = 'Shot') /
                NULLIF((SELECT matches FROM match_count)::NUMERIC, 0) AS shots_per_match,
            -- Build-up & possession
            COUNT(*) FILTER (WHERE te.event_type = 'Pass' AND te.pass_outcome IS NULL) /
                NULLIF(COUNT(*) FILTER (WHERE te.event_type = 'Pass')::NUMERIC, 0) AS pass_accuracy,
            COUNT(*) FILTER (WHERE te.event_type = 'Pass' AND te.pass_outcome IS NULL AND
                te.pass_length > 32) /
                NULLIF((SELECT matches FROM match_count)::NUMERIC, 0) AS long_passes_per_match,
            COUNT(*) FILTER (WHERE te.event_type = 'Pass' AND te.pass_outcome IS NULL AND
                (te.end_location_x - te.location_x) > 10) /
                NULLIF((SELECT matches FROM match_count)::NUMERIC, 0) AS progressive_passes_per_match,
            COUNT(*) FILTER (WHERE te.event_type = 'Carry' AND
                (te.carry_end_x - te.location_x) > 10) /
                NULLIF((SELECT matches FROM match_count)::NUMERIC, 0) AS progressive_carries_per_match,
            -- Pressing
            COUNT(*) FILTER (WHERE te.event_type = 'Pressure') /
                NULLIF((SELECT matches FROM match_count)::NUMERIC, 0) AS pressures_per_match,
            COUNT(*) FILTER (WHERE te.counterpress) /
                NULLIF((SELECT matches FROM match_count)::NUMERIC, 0) AS counterpresses_per_match,
            AVG(te.location_x) FILTER (WHERE te.event_type = 'Pressure') AS avg_pressure_height,
            -- Defensive
            COUNT(*) FILTER (WHERE te.event_type = 'Tackle') /
                NULLIF((SELECT matches FROM match_count)::NUMERIC, 0) AS tackles_per_match,
            COUNT(*) FILTER (WHERE te.event_type = 'Interception') /
                NULLIF((SELECT matches FROM match_count)::NUMERIC, 0) AS interceptions_per_match,
            AVG(te.location_x) FILTER (WHERE te.event_type IN ('Tackle', 'Interception')) AS avg_defensive_line,
            -- Set pieces
            COALESCE(SUM(te.xg) FILTER (WHERE te.event_type = 'Shot' AND
                te.play_pattern IN ('From Corner', 'From Free Kick')), 0) /
                NULLIF((SELECT matches FROM match_count)::NUMERIC, 0) AS set_piece_xg_per_match,
            -- Directness
            COUNT(*) FILTER (WHERE te.event_type = 'Shot' AND te.play_pattern = 'From Counter') /
                NULLIF(COUNT(*) FILTER (WHERE te.event_type = 'Shot')::NUMERIC, 0) AS counter_attack_shot_share,
            -- Width
            COUNT(*) FILTER (WHERE te.event_type = 'Pass' AND te.pass_outcome IS NULL AND
                (te.location_y < 20 OR te.location_y > 60)) /
                NULLIF(COUNT(*) FILTER (WHERE te.event_type = 'Pass' AND te.pass_outcome IS NULL)::NUMERIC, 0) AS wide_pass_share,
            -- Aerial
            COUNT(*) FILTER (WHERE te.event_type = 'Duel' AND te.duel_type = 'Aerial Lost') +
            COUNT(*) FILTER (WHERE te.event_type = 'Duel' AND te.duel_outcome = 'Won' AND te.duel_type LIKE '%Aerial%') AS aerial_duels,
            COUNT(*) FILTER (WHERE te.duel_outcome = 'Won' AND te.duel_type LIKE '%Aerial%') AS aerial_wins
        FROM team_events te
        CROSS JOIN match_count mc
        JOIN teams t ON t.team_id = :team_id
        GROUP BY t.team_name, mc.matches
    """)

    try:
        with engine.connect() as conn:
            result = pd.read_sql(query, conn, params=params)
    except Exception as exc:
        logger.error(f"Failed to build profile for team {team_id}: {exc}")
        return None

    if result.empty or result["matches"].iloc[0] == 0:
        return None

    row = result.iloc[0]
    return {
        "team_id": team_id,
        "team_name": row["team_name"],
        "matches": int(row["matches"]),
        "xg_per_match": float(row["xg_per_match"] or 0),
        "shots_per_match": float(row["shots_per_match"] or 0),
        "pass_accuracy": float(row["pass_accuracy"] or 0),
        "long_passes_per_match": float(row["long_passes_per_match"] or 0),
        "progressive_passes_per_match": float(row["progressive_passes_per_match"] or 0),
        "progressive_carries_per_match": float(
            row["progressive_carries_per_match"] or 0
        ),
        "pressures_per_match": float(row["pressures_per_match"] or 0),
        "counterpresses_per_match": float(row["counterpresses_per_match"] or 0),
        "avg_pressure_height": float(row["avg_pressure_height"] or 50),
        "tackles_per_match": float(row["tackles_per_match"] or 0),
        "interceptions_per_match": float(row["interceptions_per_match"] or 0),
        "avg_defensive_line": float(row["avg_defensive_line"] or 40),
        "set_piece_xg_per_match": float(row["set_piece_xg_per_match"] or 0),
        "counter_attack_shot_share": float(row["counter_attack_shot_share"] or 0),
        "wide_pass_share": float(row["wide_pass_share"] or 0),
        "aerial_duels": int(row["aerial_duels"] or 0),
        "aerial_wins": int(row["aerial_wins"] or 0),
    }


def _compare_dimensions(profile_a: dict, profile_b: dict) -> list[TacticalDimension]:
    """Compare two team profiles across tactical dimensions."""
    dimensions = []

    # 1. Pressing intensity
    press_a = profile_a["pressures_per_match"]
    press_b = profile_b["pressures_per_match"]
    press_max = max(press_a, press_b, 1)
    dimensions.append(
        TacticalDimension(
            name="Pressing Intensity",
            team_a_score=round(press_a, 1),
            team_b_score=round(press_b, 1),
            advantage=round((press_a - press_b) / press_max, 3),
            description=_pressing_description(profile_a, profile_b),
        )
    )

    # 2. Defensive line height
    line_a = profile_a["avg_defensive_line"]
    line_b = profile_b["avg_defensive_line"]
    dimensions.append(
        TacticalDimension(
            name="Defensive Line Height",
            team_a_score=round(line_a, 1),
            team_b_score=round(line_b, 1),
            advantage=round((line_a - line_b) / 60, 3),  # Normalised to pitch length
            description=_defensive_line_description(profile_a, profile_b),
        )
    )

    # 3. Build-up quality
    prog_a = (
        profile_a["progressive_passes_per_match"]
        + profile_a["progressive_carries_per_match"]
    )
    prog_b = (
        profile_b["progressive_passes_per_match"]
        + profile_b["progressive_carries_per_match"]
    )
    prog_max = max(prog_a, prog_b, 1)
    dimensions.append(
        TacticalDimension(
            name="Build-Up Progression",
            team_a_score=round(prog_a, 1),
            team_b_score=round(prog_b, 1),
            advantage=round((prog_a - prog_b) / prog_max, 3),
            description=_buildup_description(profile_a, profile_b),
        )
    )

    # 4. Set-piece threat
    sp_a = profile_a["set_piece_xg_per_match"]
    sp_b = profile_b["set_piece_xg_per_match"]
    sp_max = max(sp_a, sp_b, 0.01)
    dimensions.append(
        TacticalDimension(
            name="Set-Piece Threat",
            team_a_score=round(sp_a, 3),
            team_b_score=round(sp_b, 3),
            advantage=round((sp_a - sp_b) / sp_max, 3),
            description=_set_piece_description(profile_a, profile_b),
        )
    )

    # 5. Directness / counter-attacking
    ca_a = profile_a["counter_attack_shot_share"]
    ca_b = profile_b["counter_attack_shot_share"]
    dimensions.append(
        TacticalDimension(
            name="Counter-Attack Threat",
            team_a_score=round(ca_a, 3),
            team_b_score=round(ca_b, 3),
            advantage=round(ca_a - ca_b, 3),
            description=_counter_description(profile_a, profile_b),
        )
    )

    # 6. Width usage
    wide_a = profile_a["wide_pass_share"]
    wide_b = profile_b["wide_pass_share"]
    dimensions.append(
        TacticalDimension(
            name="Width Usage",
            team_a_score=round(wide_a, 3),
            team_b_score=round(wide_b, 3),
            advantage=round(wide_a - wide_b, 3),
            description=_width_description(profile_a, profile_b),
        )
    )

    return dimensions


def _identify_key_battles(profile_a: dict, profile_b: dict) -> list[KeyBattle]:
    """Identify key tactical battles from profile comparison."""
    battles = []

    # High press vs short build-up
    if profile_a["pressures_per_match"] > 20 and profile_b["pass_accuracy"] > 0.82:
        battles.append(
            KeyBattle(
                area="Midfield press vs build-up",
                team_a_factor=f"{profile_a['team_name']}'s high press ({profile_a['pressures_per_match']:.0f} pressures/match)",
                team_b_factor=f"{profile_b['team_name']}'s passing accuracy ({profile_b['pass_accuracy']:.0%})",
                significance="high",
                narrative=(
                    f"{profile_a['team_name']}'s aggressive pressing will test "
                    f"{profile_b['team_name']}'s ability to play through pressure. "
                    f"If {profile_b['team_name']} can retain possession under press, "
                    f"they will find space in transition."
                ),
            )
        )
    elif profile_b["pressures_per_match"] > 20 and profile_a["pass_accuracy"] > 0.82:
        battles.append(
            KeyBattle(
                area="Midfield press vs build-up",
                team_a_factor=f"{profile_a['team_name']}'s passing accuracy ({profile_a['pass_accuracy']:.0%})",
                team_b_factor=f"{profile_b['team_name']}'s high press ({profile_b['pressures_per_match']:.0f} pressures/match)",
                significance="high",
                narrative=(
                    f"{profile_b['team_name']}'s aggressive pressing will test "
                    f"{profile_a['team_name']}'s ability to play through pressure."
                ),
            )
        )

    # High line vs counter-attack
    if (
        profile_b["avg_defensive_line"] > 50
        and profile_a["counter_attack_shot_share"] > 0.15
    ):
        battles.append(
            KeyBattle(
                area="Space in behind",
                team_a_factor=f"{profile_a['team_name']}'s counter-attacking threat ({profile_a['counter_attack_shot_share']:.0%} of shots from counters)",
                team_b_factor=f"{profile_b['team_name']}'s high defensive line (avg position: {profile_b['avg_defensive_line']:.0f}m)",
                significance="high",
                narrative=(
                    f"{profile_b['team_name']}'s high line creates space for "
                    f"{profile_a['team_name']}'s counter-attacks. Quick transitions "
                    f"could be decisive."
                ),
            )
        )
    elif (
        profile_a["avg_defensive_line"] > 50
        and profile_b["counter_attack_shot_share"] > 0.15
    ):
        battles.append(
            KeyBattle(
                area="Space in behind",
                team_a_factor=f"{profile_a['team_name']}'s high defensive line (avg: {profile_a['avg_defensive_line']:.0f}m)",
                team_b_factor=f"{profile_b['team_name']}'s counter-attacking threat ({profile_b['counter_attack_shot_share']:.0%} from counters)",
                significance="high",
                narrative=(
                    f"{profile_a['team_name']}'s high line is vulnerable to "
                    f"{profile_b['team_name']}'s direct counter-attacks."
                ),
            )
        )

    # Set-piece advantage
    sp_diff = abs(
        profile_a["set_piece_xg_per_match"] - profile_b["set_piece_xg_per_match"]
    )
    if sp_diff > 0.1:
        stronger = (
            profile_a
            if profile_a["set_piece_xg_per_match"] > profile_b["set_piece_xg_per_match"]
            else profile_b
        )
        weaker = profile_b if stronger == profile_a else profile_a
        battles.append(
            KeyBattle(
                area="Set pieces",
                team_a_factor=f"{profile_a['team_name']}: {profile_a['set_piece_xg_per_match']:.2f} set-piece xG/match",
                team_b_factor=f"{profile_b['team_name']}: {profile_b['set_piece_xg_per_match']:.2f} set-piece xG/match",
                significance="medium",
                narrative=(
                    f"{stronger['team_name']} generates significantly more threat from "
                    f"set pieces. Defending corners and free kicks will be critical for "
                    f"{weaker['team_name']}."
                ),
            )
        )

    # Wide play vs narrow defence
    if profile_a["wide_pass_share"] > 0.35 or profile_b["wide_pass_share"] > 0.35:
        wider = (
            profile_a
            if profile_a["wide_pass_share"] > profile_b["wide_pass_share"]
            else profile_b
        )
        other = profile_b if wider == profile_a else profile_a
        battles.append(
            KeyBattle(
                area="Wide areas",
                team_a_factor=f"{profile_a['team_name']}: {profile_a['wide_pass_share']:.0%} passes in wide zones",
                team_b_factor=f"{profile_b['team_name']}: {profile_b['wide_pass_share']:.0%} passes in wide zones",
                significance="medium",
                narrative=(
                    f"{wider['team_name']} heavily utilises wide areas. "
                    f"Fullback matchups and wide defensive coverage will be key."
                ),
            )
        )

    return battles


def _compute_overall_advantage(dimensions: list[TacticalDimension]) -> float:
    """Compute aggregate tactical advantage score."""
    if not dimensions:
        return 0.0
    advantages = [d.advantage for d in dimensions]
    return round(float(np.mean(advantages)), 3)


# --- Narrative generation helpers ---


def _pressing_description(a: dict, b: dict) -> str:
    name_a, name_b = a["team_name"], b["team_name"]
    if a["pressures_per_match"] > b["pressures_per_match"] * 1.2:
        return f"{name_a} presses significantly more aggressively ({a['pressures_per_match']:.0f} vs {b['pressures_per_match']:.0f} per match)"
    elif b["pressures_per_match"] > a["pressures_per_match"] * 1.2:
        return f"{name_b} presses significantly more aggressively ({b['pressures_per_match']:.0f} vs {a['pressures_per_match']:.0f} per match)"
    return f"Similar pressing intensity ({a['pressures_per_match']:.0f} vs {b['pressures_per_match']:.0f} per match)"


def _defensive_line_description(a: dict, b: dict) -> str:
    name_a, name_b = a["team_name"], b["team_name"]
    if a["avg_defensive_line"] > b["avg_defensive_line"] + 5:
        return f"{name_a} holds a significantly higher defensive line ({a['avg_defensive_line']:.0f}m vs {b['avg_defensive_line']:.0f}m)"
    elif b["avg_defensive_line"] > a["avg_defensive_line"] + 5:
        return f"{name_b} holds a significantly higher defensive line ({b['avg_defensive_line']:.0f}m vs {a['avg_defensive_line']:.0f}m)"
    return f"Similar defensive line heights ({a['avg_defensive_line']:.0f}m vs {b['avg_defensive_line']:.0f}m)"


def _buildup_description(a: dict, b: dict) -> str:
    prog_a = a["progressive_passes_per_match"] + a["progressive_carries_per_match"]
    prog_b = b["progressive_passes_per_match"] + b["progressive_carries_per_match"]
    name_a, name_b = a["team_name"], b["team_name"]
    if prog_a > prog_b * 1.2:
        return f"{name_a} progresses the ball more effectively ({prog_a:.0f} vs {prog_b:.0f} progressive actions per match)"
    elif prog_b > prog_a * 1.2:
        return f"{name_b} progresses the ball more effectively ({prog_b:.0f} vs {prog_a:.0f} progressive actions per match)"
    return f"Similar ball progression rates ({prog_a:.0f} vs {prog_b:.0f} per match)"


def _set_piece_description(a: dict, b: dict) -> str:
    name_a, name_b = a["team_name"], b["team_name"]
    sp_a, sp_b = a["set_piece_xg_per_match"], b["set_piece_xg_per_match"]
    if sp_a > sp_b * 1.5:
        return f"{name_a} is significantly more dangerous from set pieces ({sp_a:.2f} vs {sp_b:.2f} xG per match)"
    elif sp_b > sp_a * 1.5:
        return f"{name_b} is significantly more dangerous from set pieces ({sp_b:.2f} vs {sp_a:.2f} xG per match)"
    return f"Similar set-piece threat levels ({sp_a:.2f} vs {sp_b:.2f} xG per match)"


def _counter_description(a: dict, b: dict) -> str:
    name_a, name_b = a["team_name"], b["team_name"]
    ca_a, ca_b = a["counter_attack_shot_share"], b["counter_attack_shot_share"]
    if ca_a > ca_b + 0.1:
        return f"{name_a} generates a higher proportion of shots from counter-attacks ({ca_a:.0%} vs {ca_b:.0%})"
    elif ca_b > ca_a + 0.1:
        return f"{name_b} generates a higher proportion of shots from counter-attacks ({ca_b:.0%} vs {ca_a:.0%})"
    return f"Similar counter-attacking profiles ({ca_a:.0%} vs {ca_b:.0%} of shots from counters)"


def _width_description(a: dict, b: dict) -> str:
    name_a, name_b = a["team_name"], b["team_name"]
    w_a, w_b = a["wide_pass_share"], b["wide_pass_share"]
    if w_a > w_b + 0.05:
        return f"{name_a} uses width more heavily ({w_a:.0%} vs {w_b:.0%} of passes in wide zones)"
    elif w_b > w_a + 0.05:
        return f"{name_b} uses width more heavily ({w_b:.0%} vs {w_a:.0%} of passes in wide zones)"
    return f"Similar width usage ({w_a:.0%} vs {w_b:.0%})"


def _generate_narrative(
    profile_a: dict, profile_b: dict, dimensions: list[TacticalDimension]
) -> str:
    """Generate a coaching-friendly tactical narrative."""
    name_a = profile_a["team_name"]
    name_b = profile_b["team_name"]

    parts = []

    # Identify dominant dimensions
    biggest_advantages = sorted(
        dimensions, key=lambda d: abs(d.advantage), reverse=True
    )

    for dim in biggest_advantages[:3]:
        if abs(dim.advantage) > 0.15:
            parts.append(dim.description + ".")

    if not parts:
        parts.append(
            f"{name_a} and {name_b} are tactically well-matched across most dimensions."
        )

    return " ".join(parts)


def _generate_recommendations(
    profile_a: dict, profile_b: dict, dimensions: list[TacticalDimension]
) -> list[str]:
    """Generate tactical recommendations for team A against team B."""
    recs = []
    name_b = profile_b["team_name"]

    # Exploit high line
    if profile_b["avg_defensive_line"] > 50:
        recs.append(
            f"Exploit space behind {name_b}'s high line with direct balls and quick transitions."
        )

    # Manage pressing
    if profile_b["pressures_per_match"] > 22:
        recs.append(
            f"Expect intense pressing from {name_b}. Prepare rehearsed press-breaking patterns and consider longer direct passes to bypass the press."
        )

    # Set-piece opportunity
    if (
        profile_b["set_piece_xg_per_match"] < 0.1
        and profile_a["set_piece_xg_per_match"] > 0.15
    ):
        recs.append(
            "Set pieces represent a significant advantage. Prioritise winning corners and free kicks in dangerous areas."
        )

    # Counter-attack defence
    if profile_b["counter_attack_shot_share"] > 0.15:
        recs.append(
            f"{name_b} is dangerous on the counter. Maintain defensive balance during attacks and manage transition moments."
        )

    # Wide vulnerability
    if profile_b["wide_pass_share"] > 0.35:
        recs.append(
            f"{name_b} relies heavily on wide areas. Compact defensive shape and disciplined fullback positioning will limit their supply."
        )

    if not recs:
        recs.append(
            "No significant tactical vulnerabilities identified. Focus on executing own game plan."
        )

    return recs
