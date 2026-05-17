"""Set-piece analysis module — corner kicks, free kicks, and throw-ins.

Provides tactical insights for set-piece coaching:
- Delivery clustering (near post, far post, short, penalty spot)
- Outcome modelling (xG from set pieces, conversion rates)
- Routine identification (repeated patterns across matches)
- Defensive vulnerabilities on conceded set pieces

Set pieces account for ~30% of goals in professional football,
making this analysis high-value for coaching staff.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist

logger = logging.getLogger(__name__)


class SetPieceType(str, Enum):
    """Types of set pieces analysed."""

    CORNER = "corner"
    FREE_KICK = "free_kick"
    THROW_IN = "throw_in"
    PENALTY = "penalty"
    GOAL_KICK = "goal_kick"


class DeliveryZone(str, Enum):
    """Target zone for set-piece deliveries."""

    NEAR_POST = "near_post"
    FAR_POST = "far_post"
    PENALTY_SPOT = "penalty_spot"
    EDGE_OF_BOX = "edge_of_box"
    SHORT = "short"
    SIX_YARD_BOX = "six_yard_box"
    DEEP = "deep"


@dataclass
class SetPieceSequence:
    """A set-piece event and its subsequent actions until possession change."""

    match_id: int
    team_id: int
    set_piece_type: SetPieceType
    delivery_zone: DeliveryZone
    taker_id: int | None
    taker_name: str | None
    start_x: float
    start_y: float
    delivery_x: float
    delivery_y: float
    events: pd.DataFrame
    outcome: str  # goal, shot_on_target, shot_off_target, cleared, turnover
    xg_generated: float
    num_actions: int
    is_inswinger: bool | None = None
    is_outswinger: bool | None = None


def extract_set_pieces(events_df: pd.DataFrame) -> list[SetPieceSequence]:
    """Extract set-piece sequences from event data.

    Identifies set-piece origins and tracks subsequent events until
    possession changes or play resets.

    Args:
        events_df: Full match event DataFrame with standard columns.

    Returns:
        List of SetPieceSequence objects.
    """
    required_cols = {"match_id", "team_id", "event_type", "play_pattern", "minute"}
    missing = required_cols - set(events_df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = events_df.sort_values(["match_id", "minute", "second"]).reset_index(drop=True)

    # Identify set-piece origins
    sp_mask = df["play_pattern"].isin(
        ["From Corner", "From Free Kick", "From Throw In", "From Goal Kick"]
    )

    sequences = []
    processed_possessions = set()

    for idx in df[sp_mask].index:
        row = df.loc[idx]
        match_id = row["match_id"]
        possession = row.get("possession")

        # Skip if we already processed this possession
        key = (match_id, possession)
        if key in processed_possessions:
            continue
        processed_possessions.add(key)

        # Get all events in this possession
        poss_events = df[
            (df["match_id"] == match_id) & (df["possession"] == possession)
        ]
        if poss_events.empty:
            continue

        team_id = int(row["team_id"])
        sp_type = _classify_set_piece_type(row["play_pattern"])

        # Delivery location
        delivery_x, delivery_y = _get_delivery_location(poss_events)

        # Classify delivery zone
        zone = _classify_delivery_zone(delivery_x, delivery_y, sp_type)

        # Determine outcome
        outcome, xg_gen = _determine_outcome(poss_events)

        # Taker info
        taker_id = int(row["player_id"]) if pd.notna(row.get("player_id")) else None
        taker_name = row.get("player_name")

        seq = SetPieceSequence(
            match_id=int(match_id),
            team_id=team_id,
            set_piece_type=sp_type,
            delivery_zone=zone,
            taker_id=taker_id,
            taker_name=str(taker_name) if taker_name else None,
            start_x=float(row.get("location_x", 0) or 0),
            start_y=float(row.get("location_y", 0) or 0),
            delivery_x=delivery_x,
            delivery_y=delivery_y,
            events=poss_events,
            outcome=outcome,
            xg_generated=xg_gen,
            num_actions=len(poss_events),
        )

        # Swing classification for corners
        if sp_type == SetPieceType.CORNER and "pass_type" in poss_events.columns:
            first_pass = poss_events[poss_events["event_type"] == "Pass"].head(1)
            if not first_pass.empty:
                pass_type = first_pass.iloc[0].get("pass_type", "")
                seq.is_inswinger = pass_type == "Inswinging"
                seq.is_outswinger = pass_type == "Outswinging"

        sequences.append(seq)

    logger.info("Extracted %d set-piece sequences", len(sequences))
    return sequences


def _classify_set_piece_type(play_pattern: str) -> SetPieceType:
    """Map play_pattern string to SetPieceType enum."""
    mapping = {
        "From Corner": SetPieceType.CORNER,
        "From Free Kick": SetPieceType.FREE_KICK,
        "From Throw In": SetPieceType.THROW_IN,
        "From Goal Kick": SetPieceType.GOAL_KICK,
    }
    return mapping.get(play_pattern, SetPieceType.FREE_KICK)


def _get_delivery_location(events: pd.DataFrame) -> tuple[float, float]:
    """Get the delivery target (end location of first pass)."""
    passes = events[events["event_type"] == "Pass"]
    if not passes.empty and "end_location_x" in passes.columns:
        first_pass = passes.iloc[0]
        x = float(first_pass.get("end_location_x", 0) or 0)
        y = float(first_pass.get("end_location_y", 0) or 0)
        return x, y
    return 0.0, 0.0


def _classify_delivery_zone(x: float, y: float, sp_type: SetPieceType) -> DeliveryZone:
    """Classify delivery target into a tactical zone."""
    if x == 0 and y == 0:
        return DeliveryZone.SHORT

    # For corners: relative to goal
    if sp_type == SetPieceType.CORNER:
        if x >= 114:  # 6-yard box area
            if y < 35:
                return DeliveryZone.NEAR_POST
            elif y > 45:
                return DeliveryZone.FAR_POST
            else:
                return DeliveryZone.SIX_YARD_BOX
        elif x >= 102:  # Penalty area
            if 35 <= y <= 45:
                return DeliveryZone.PENALTY_SPOT
            else:
                return DeliveryZone.NEAR_POST if y < 40 else DeliveryZone.FAR_POST
        else:
            return DeliveryZone.EDGE_OF_BOX

    # For free kicks
    if sp_type == SetPieceType.FREE_KICK:
        if x >= 114:
            return DeliveryZone.SIX_YARD_BOX
        elif x >= 102:
            return DeliveryZone.PENALTY_SPOT
        elif x >= 80:
            return DeliveryZone.EDGE_OF_BOX
        else:
            return DeliveryZone.DEEP

    return DeliveryZone.SHORT


def _determine_outcome(events: pd.DataFrame) -> tuple[str, float]:
    """Determine the outcome of a set-piece sequence."""
    xg_total = 0.0
    if "xg" in events.columns:
        xg_total = float(events["xg"].sum()) if events["xg"].notna().any() else 0.0

    shots = events[events["event_type"] == "Shot"]
    if not shots.empty and "shot_outcome" in shots.columns:
        if (shots["shot_outcome"] == "Goal").any():
            return "goal", xg_total
        if shots["shot_outcome"].isin(["Saved", "Saved to Post"]).any():
            return "shot_on_target", xg_total
        return "shot_off_target", xg_total

    # Check for clearances (defensive success)
    if (events["event_type"] == "Clearance").any():
        return "cleared", xg_total

    return "turnover", xg_total


def set_pieces_to_dataframe(sequences: list[SetPieceSequence]) -> pd.DataFrame:
    """Convert set-piece sequences to a summary DataFrame."""
    records = []
    for sp in sequences:
        records.append({
            "match_id": sp.match_id,
            "team_id": sp.team_id,
            "set_piece_type": sp.set_piece_type.value,
            "delivery_zone": sp.delivery_zone.value,
            "taker_id": sp.taker_id,
            "taker_name": sp.taker_name,
            "start_x": sp.start_x,
            "start_y": sp.start_y,
            "delivery_x": sp.delivery_x,
            "delivery_y": sp.delivery_y,
            "outcome": sp.outcome,
            "xg_generated": sp.xg_generated,
            "num_actions": sp.num_actions,
            "is_inswinger": sp.is_inswinger,
            "is_outswinger": sp.is_outswinger,
        })
    return pd.DataFrame(records)


def compute_set_piece_efficiency(sp_df: pd.DataFrame, team_id: int) -> dict[str, Any]:
    """Compute set-piece efficiency metrics for a team.

    Args:
        sp_df: DataFrame from set_pieces_to_dataframe().
        team_id: Team to analyse.

    Returns:
        Dictionary with efficiency metrics by set-piece type.
    """
    team_sp = sp_df[sp_df["team_id"] == team_id]

    if team_sp.empty:
        return {"team_id": team_id, "total_set_pieces": 0}

    result: dict[str, Any] = {
        "team_id": team_id,
        "total_set_pieces": len(team_sp),
    }

    for sp_type in SetPieceType:
        type_sp = team_sp[team_sp["set_piece_type"] == sp_type.value]
        if type_sp.empty:
            continue

        goals = (type_sp["outcome"] == "goal").sum()
        shots = type_sp["outcome"].isin(["goal", "shot_on_target", "shot_off_target"]).sum()

        result[f"{sp_type.value}_count"] = len(type_sp)
        result[f"{sp_type.value}_shot_rate"] = round(shots / len(type_sp), 3)
        result[f"{sp_type.value}_goal_rate"] = round(goals / len(type_sp), 3)
        result[f"{sp_type.value}_xg_total"] = round(type_sp["xg_generated"].sum(), 2)
        result[f"{sp_type.value}_xg_per_attempt"] = round(type_sp["xg_generated"].mean(), 4)

    return result


def cluster_delivery_patterns(
    sp_df: pd.DataFrame,
    team_id: int,
    sp_type: str = "corner",
    n_clusters: int = 4,
) -> pd.DataFrame:
    """Cluster delivery patterns to identify repeated routines.

    Uses hierarchical clustering on delivery locations to find
    tactical patterns (e.g., always near post, short corner routine).

    Args:
        sp_df: Set-piece DataFrame.
        team_id: Team to analyse.
        sp_type: Type filter (corner, free_kick, etc).
        n_clusters: Number of clusters to form.

    Returns:
        DataFrame with cluster assignments and centroids.
    """
    filtered = sp_df[
        (sp_df["team_id"] == team_id) & (sp_df["set_piece_type"] == sp_type)
    ].copy()

    if len(filtered) < n_clusters:
        filtered["cluster"] = 0
        return filtered

    # Cluster on delivery location
    coords = filtered[["delivery_x", "delivery_y"]].fillna(0).values

    if len(coords) < 2:
        filtered["cluster"] = 0
        return filtered

    dist_matrix = pdist(coords)
    linkage_matrix = linkage(dist_matrix, method="ward")
    filtered["cluster"] = fcluster(linkage_matrix, t=n_clusters, criterion="maxclust")

    return filtered


def compute_defensive_set_piece_vulnerabilities(
    sp_df: pd.DataFrame,
    events_df: pd.DataFrame,
    team_id: int,
) -> dict[str, Any]:
    """Analyse set pieces conceded by a team to find defensive weaknesses.

    Args:
        sp_df: Set-piece DataFrame (all teams).
        events_df: Full event DataFrame.
        team_id: Team whose defence to analyse.

    Returns:
        Dictionary with defensive vulnerability metrics.
    """
    # Set pieces where the opponent is attacking (not our team)
    conceded = sp_df[sp_df["team_id"] != team_id].copy()

    # Filter to matches involving our team
    if "match_id" in events_df.columns:
        our_matches = events_df[events_df["team_id"] == team_id]["match_id"].unique()
        conceded = conceded[conceded["match_id"].isin(our_matches)]

    if conceded.empty:
        return {"team_id": team_id, "set_pieces_conceded": 0}

    goals_conceded = (conceded["outcome"] == "goal").sum()
    shots_conceded = conceded["outcome"].isin(
        ["goal", "shot_on_target", "shot_off_target"]
    ).sum()

    # Most dangerous delivery zones conceded
    zone_xg = conceded.groupby("delivery_zone")["xg_generated"].agg(["sum", "count", "mean"])
    most_dangerous_zone = zone_xg["sum"].idxmax() if not zone_xg.empty else "unknown"

    return {
        "team_id": team_id,
        "set_pieces_conceded": len(conceded),
        "goals_conceded_from_sp": int(goals_conceded),
        "shots_conceded_from_sp": int(shots_conceded),
        "xg_conceded_from_sp": round(conceded["xg_generated"].sum(), 2),
        "most_dangerous_zone": most_dangerous_zone,
        "zone_breakdown": zone_xg.to_dict() if not zone_xg.empty else {},
        "conceded_by_type": conceded["set_piece_type"].value_counts().to_dict(),
    }
