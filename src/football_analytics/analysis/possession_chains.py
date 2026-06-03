"""Possession chain analysis — sequence modelling of build-up play.

Analyses connected sequences of events within a possession to identify:
- Build-up patterns (short passing, long balls, wing play, central penetration)
- Transition speed (counter-attacks vs patient build-up)
- Chain outcomes (shot, goal, turnover, foul won)
- Key progression events within chains
- Dangerous possession indicators

Implements the concept from Lucey et al. and Decroos et al. (VAEP-style)
but simplified for event-level StatsBomb data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class ChainOutcome(str, Enum):
    """How a possession chain ended."""

    GOAL = "goal"
    SHOT = "shot"
    SHOT_ON_TARGET = "shot_on_target"
    KEY_PASS = "key_pass"
    TURNOVER = "turnover"
    FOUL_WON = "foul_won"
    CORNER_WON = "corner_won"
    OUT_OF_PLAY = "out_of_play"
    OTHER = "other"


class BuildUpStyle(str, Enum):
    """Classification of build-up pattern."""

    SHORT_PASSING = "short_passing"
    LONG_BALL = "long_ball"
    WING_PLAY = "wing_play"
    CENTRAL_PENETRATION = "central_penetration"
    COUNTER_ATTACK = "counter_attack"
    SET_PIECE = "set_piece"
    MIXED = "mixed"


@dataclass
class PossessionChain:
    """A connected sequence of events within one possession."""

    match_id: int
    possession_number: int
    team_id: int
    events: pd.DataFrame
    start_x: float = 0.0
    start_y: float = 0.0
    end_x: float = 0.0
    end_y: float = 0.0
    duration_seconds: float = 0.0
    num_events: int = 0
    num_passes: int = 0
    progressive_distance: float = 0.0
    outcome: ChainOutcome = ChainOutcome.OTHER
    style: BuildUpStyle = BuildUpStyle.MIXED
    xg_generated: float = 0.0
    entered_final_third: bool = False
    entered_box: bool = False


def extract_possession_chains(events_df: pd.DataFrame) -> list[PossessionChain]:
    """Extract possession chains from event-level data.

    Groups events by (match_id, possession) and analyses each sequence.

    Args:
        events_df: Event-level DataFrame with standard StatsBomb columns.
                   Must include: match_id, possession, team_id, event_type,
                   location_x, location_y, minute, second.

    Returns:
        List of PossessionChain objects with computed metrics.
    """
    required_cols = {"match_id", "possession", "team_id", "event_type", "minute"}
    missing = required_cols - set(events_df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    chains = []
    grouped = events_df.sort_values(["match_id", "minute", "second"]).groupby(["match_id", "possession"])

    for (match_id, poss_num), group in grouped:
        if len(group) < 2:
            continue

        # Determine possession team (most common team_id in the chain)
        team_id = group["team_id"].mode().iloc[0]
        team_events = group[group["team_id"] == team_id]

        if team_events.empty:
            continue

        chain = PossessionChain(
            match_id=int(match_id),
            possession_number=int(poss_num),
            team_id=int(team_id),
            events=group,
        )

        # Spatial extent
        if "location_x" in group.columns:
            valid_locs = group.dropna(subset=["location_x", "location_y"])
            if not valid_locs.empty:
                chain.start_x = float(valid_locs.iloc[0]["location_x"])
                chain.start_y = float(valid_locs.iloc[0]["location_y"])
                chain.end_x = float(valid_locs.iloc[-1]["location_x"])
                chain.end_y = float(valid_locs.iloc[-1]["location_y"])

        # Duration
        start_time = group.iloc[0]["minute"] * 60 + group.iloc[0].get("second", 0)
        end_time = group.iloc[-1]["minute"] * 60 + group.iloc[-1].get("second", 0)
        chain.duration_seconds = max(0, end_time - start_time)

        # Event counts
        chain.num_events = len(group)
        chain.num_passes = int((group["event_type"] == "Pass").sum())

        # Progressive distance (net x-distance towards goal)
        chain.progressive_distance = max(0, chain.end_x - chain.start_x)

        # Zone entries
        if "location_x" in group.columns:
            chain.entered_final_third = bool((group["location_x"] >= 80).any())
            chain.entered_box = bool(
                ((group["location_x"] >= 102) & (group["location_y"] >= 18) & (group["location_y"] <= 62)).any()
            )

        # Outcome classification
        chain.outcome = _classify_outcome(group)

        # xG generated
        if "xg" in group.columns:
            chain.xg_generated = float(group["xg"].sum()) if group["xg"].notna().any() else 0.0

        # Build-up style classification
        chain.style = _classify_style(group, chain)

        chains.append(chain)

    logger.info("Extracted %d possession chains from %d events", len(chains), len(events_df))
    return chains


def _classify_outcome(events: pd.DataFrame) -> ChainOutcome:
    """Classify how a possession chain ended."""
    last_events = events.tail(3)

    if (last_events["event_type"] == "Shot").any():
        shots = last_events[last_events["event_type"] == "Shot"]
        if "shot_outcome" in shots.columns:
            if (shots["shot_outcome"] == "Goal").any():
                return ChainOutcome.GOAL
            if (shots["shot_outcome"].isin(["Saved", "Saved to Post"])).any():
                return ChainOutcome.SHOT_ON_TARGET
        return ChainOutcome.SHOT

    if "key_pass" in events.columns and events["key_pass"].any():
        return ChainOutcome.KEY_PASS

    last_event_type = events.iloc[-1]["event_type"]
    if last_event_type in ("Dispossessed", "Miscontrol", "Error"):
        return ChainOutcome.TURNOVER
    if last_event_type == "Foul Won":
        return ChainOutcome.FOUL_WON

    # Check for failed passes (turnovers)
    if "pass_outcome" in events.columns and events.iloc[-1].get("pass_outcome") in (
        "Incomplete",
        "Out",
        "Offside",
    ):
        return ChainOutcome.TURNOVER

    return ChainOutcome.OTHER


def _classify_style(events: pd.DataFrame, chain: PossessionChain) -> BuildUpStyle:
    """Classify the build-up style of a possession chain."""
    # Quick transitions (< 10 seconds, gaining > 40m)
    if chain.duration_seconds < 10 and chain.progressive_distance > 40:
        return BuildUpStyle.COUNTER_ATTACK

    # Set piece origins
    if "play_pattern" in events.columns:
        first_pattern = events.iloc[0].get("play_pattern", "")
        if first_pattern in ("From Corner", "From Free Kick", "From Throw In"):
            return BuildUpStyle.SET_PIECE

    passes = events[events["event_type"] == "Pass"]
    if passes.empty:
        return BuildUpStyle.MIXED

    # Long ball (average pass length > 30m or >50% passes are long)
    if "pass_length" in passes.columns and passes["pass_length"].notna().any():
        avg_length = passes["pass_length"].mean()
        long_ratio = (passes["pass_length"] > 32).mean()
        if avg_length > 30 or long_ratio > 0.5:
            return BuildUpStyle.LONG_BALL

    # Wing play (>60% of passes in wide areas)
    if "location_y" in passes.columns and passes["location_y"].notna().any():
        wide_passes = ((passes["location_y"] < 20) | (passes["location_y"] > 60)).mean()
        if wide_passes > 0.6:
            return BuildUpStyle.WING_PLAY

    # Central penetration (>60% in central areas with progression)
    if "location_y" in passes.columns and passes["location_y"].notna().any():
        central_passes = ((passes["location_y"] >= 25) & (passes["location_y"] <= 55)).mean()
        if central_passes > 0.6 and chain.progressive_distance > 20:
            return BuildUpStyle.CENTRAL_PENETRATION

    # Short passing (many passes, low avg length)
    if (
        chain.num_passes >= 5
        and "pass_length" in passes.columns
        and passes["pass_length"].notna().any()
        and passes["pass_length"].mean() < 18
    ):
        return BuildUpStyle.SHORT_PASSING

    return BuildUpStyle.MIXED


def chains_to_dataframe(chains: list[PossessionChain]) -> pd.DataFrame:
    """Convert list of PossessionChain objects to a summary DataFrame.

    Args:
        chains: List of extracted possession chains.

    Returns:
        DataFrame with one row per chain and key metrics.
    """
    records = []
    for c in chains:
        records.append(
            {
                "match_id": c.match_id,
                "possession_number": c.possession_number,
                "team_id": c.team_id,
                "start_x": c.start_x,
                "start_y": c.start_y,
                "end_x": c.end_x,
                "end_y": c.end_y,
                "duration_seconds": c.duration_seconds,
                "num_events": c.num_events,
                "num_passes": c.num_passes,
                "progressive_distance": c.progressive_distance,
                "outcome": c.outcome.value,
                "style": c.style.value,
                "xg_generated": c.xg_generated,
                "entered_final_third": c.entered_final_third,
                "entered_box": c.entered_box,
            }
        )
    return pd.DataFrame(records)


def compute_team_possession_profile(chains_df: pd.DataFrame, team_id: int) -> dict[str, Any]:
    """Compute possession profile metrics for a team.

    Args:
        chains_df: DataFrame from chains_to_dataframe().
        team_id: Team to analyse.

    Returns:
        Dictionary with possession profile metrics.
    """
    team_chains = chains_df[chains_df["team_id"] == team_id]

    if team_chains.empty:
        return {"team_id": team_id, "total_chains": 0}

    total = len(team_chains)
    style_dist = team_chains["style"].value_counts(normalize=True).to_dict()
    outcome_dist = team_chains["outcome"].value_counts(normalize=True).to_dict()

    dangerous_chains = team_chains[team_chains["outcome"].isin(["goal", "shot", "shot_on_target", "key_pass"])]

    return {
        "team_id": team_id,
        "total_chains": total,
        "avg_chain_length_events": round(team_chains["num_events"].mean(), 1),
        "avg_chain_duration_seconds": round(team_chains["duration_seconds"].mean(), 1),
        "avg_passes_per_chain": round(team_chains["num_passes"].mean(), 1),
        "avg_progressive_distance": round(team_chains["progressive_distance"].mean(), 1),
        "final_third_entry_rate": round(team_chains["entered_final_third"].mean(), 3),
        "box_entry_rate": round(team_chains["entered_box"].mean(), 3),
        "dangerous_possession_rate": round(len(dangerous_chains) / total, 3) if total else 0,
        "total_xg_from_chains": round(team_chains["xg_generated"].sum(), 2),
        "xg_per_chain": round(team_chains["xg_generated"].mean(), 4),
        "style_distribution": style_dist,
        "outcome_distribution": outcome_dist,
    }


def compare_possession_styles(chains_df: pd.DataFrame, team_id_a: int, team_id_b: int) -> pd.DataFrame:
    """Compare possession profiles between two teams.

    Args:
        chains_df: DataFrame from chains_to_dataframe().
        team_id_a: First team.
        team_id_b: Second team.

    Returns:
        Comparison DataFrame with metrics side-by-side.
    """
    profile_a = compute_team_possession_profile(chains_df, team_id_a)
    profile_b = compute_team_possession_profile(chains_df, team_id_b)

    # Extract scalar metrics (exclude distributions)
    scalar_keys = [k for k in profile_a if not isinstance(profile_a[k], dict)]
    comparison = pd.DataFrame(
        {
            "metric": scalar_keys,
            "team_a": [profile_a[k] for k in scalar_keys],
            "team_b": [profile_b[k] for k in scalar_keys],
        }
    )
    return comparison


def identify_dangerous_sequences(
    chains: list[PossessionChain],
    min_xg: float = 0.1,
    min_progressive_distance: float = 30.0,
) -> list[PossessionChain]:
    """Filter chains to find the most dangerous attacking sequences.

    Args:
        chains: List of all possession chains.
        min_xg: Minimum xG generated to qualify.
        min_progressive_distance: Minimum forward advancement.

    Returns:
        Filtered list of dangerous possession chains.
    """
    dangerous = [
        c
        for c in chains
        if (c.xg_generated >= min_xg or c.outcome in (ChainOutcome.GOAL, ChainOutcome.SHOT_ON_TARGET))
        and c.progressive_distance >= min_progressive_distance
    ]
    return sorted(dangerous, key=lambda c: c.xg_generated, reverse=True)


def compute_transition_metrics(chains: list[PossessionChain]) -> dict[str, Any]:
    """Compute transition-specific metrics from chains.

    Analyses counter-attacks and fast transitions separately from
    patient build-ups.

    Args:
        chains: List of possession chains.

    Returns:
        Dictionary with transition vs build-up comparison.
    """
    counters = [c for c in chains if c.style == BuildUpStyle.COUNTER_ATTACK]
    patient = [
        c for c in chains if c.style in (BuildUpStyle.SHORT_PASSING, BuildUpStyle.MIXED) and c.duration_seconds > 15
    ]

    def _chain_stats(chain_list: list[PossessionChain]) -> dict[str, float]:
        if not chain_list:
            return {"count": 0, "xg_total": 0, "xg_per_chain": 0, "goal_rate": 0}
        total_xg = sum(c.xg_generated for c in chain_list)
        goals = sum(1 for c in chain_list if c.outcome == ChainOutcome.GOAL)
        return {
            "count": len(chain_list),
            "xg_total": round(total_xg, 2),
            "xg_per_chain": round(total_xg / len(chain_list), 4),
            "goal_rate": round(goals / len(chain_list), 3),
            "avg_duration": round(sum(c.duration_seconds for c in chain_list) / len(chain_list), 1),
        }

    return {
        "counter_attacks": _chain_stats(counters),
        "patient_build_up": _chain_stats(patient),
    }
