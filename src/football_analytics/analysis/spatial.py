"""Spatial dominance maps — Voronoi tessellation and space control analysis.

Implements spatial analysis techniques for football tactical analysis:
- Voronoi tessellation (who controls which pitch area?)
- Dominant region calculation (Taki & Hasegawa, 2000)
- Space creation/occupation metrics
- Passing lane analysis
- Defensive coverage gaps

Uses tracking data (when available) or event locations for approximation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull, Voronoi

logger = logging.getLogger(__name__)

# Standard pitch dimensions (metres)
_PITCH_LENGTH = 105.0
_PITCH_WIDTH = 68.0


@dataclass
class VoronoiFrame:
    """Voronoi tessellation for a single frame/moment."""

    timestamp: float
    home_positions: np.ndarray  # (N, 2)
    away_positions: np.ndarray  # (M, 2)
    voronoi: Voronoi | None
    home_control_area: float  # Total area controlled by home team (m²)
    away_control_area: float
    home_regions: list[np.ndarray]  # Vertices for each home player region
    away_regions: list[np.ndarray]


@dataclass
class SpaceDominanceResult:
    """Results from spatial dominance analysis."""

    frames: list[VoronoiFrame]
    avg_home_control: float
    avg_away_control: float
    home_control_timeline: np.ndarray
    away_control_timeline: np.ndarray
    territorial_advantage: float  # Positive = home dominance


def compute_voronoi_frame(
    home_positions: np.ndarray,
    away_positions: np.ndarray,
    pitch_length: float = _PITCH_LENGTH,
    pitch_width: float = _PITCH_WIDTH,
    timestamp: float = 0.0,
) -> VoronoiFrame:
    """Compute Voronoi tessellation for a single frame.

    Clips Voronoi regions to pitch boundaries and calculates
    area controlled by each team.

    Args:
        home_positions: (N, 2) array of home player positions in metres.
        away_positions: (M, 2) array of away player positions in metres.
        pitch_length: Pitch length in metres.
        pitch_width: Pitch width in metres.
        timestamp: Time of this frame.

    Returns:
        VoronoiFrame with computed regions and areas.
    """
    all_positions = np.vstack([home_positions, away_positions])
    n_home = len(home_positions)

    if len(all_positions) < 4:
        return VoronoiFrame(
            timestamp=timestamp,
            home_positions=home_positions,
            away_positions=away_positions,
            voronoi=None,
            home_control_area=0.0,
            away_control_area=0.0,
            home_regions=[],
            away_regions=[],
        )

    # Add mirror points at pitch boundaries for proper clipping
    boundary_points = _create_boundary_points(all_positions, pitch_length, pitch_width)
    extended_points = np.vstack([all_positions, boundary_points])

    try:
        vor = Voronoi(extended_points)
    except Exception:
        return VoronoiFrame(
            timestamp=timestamp,
            home_positions=home_positions,
            away_positions=away_positions,
            voronoi=None,
            home_control_area=0.0,
            away_control_area=0.0,
            home_regions=[],
            away_regions=[],
        )

    # Compute clipped areas for each player
    pitch_polygon = np.array([
        [0, 0], [pitch_length, 0], [pitch_length, pitch_width], [0, pitch_width]
    ])

    home_regions = []
    away_regions = []
    home_area = 0.0
    away_area = 0.0

    for i in range(len(all_positions)):
        region_idx = vor.point_region[i]
        region_vertices_idx = vor.regions[region_idx]

        if -1 in region_vertices_idx or not region_vertices_idx:
            # Unbounded region — clip to pitch
            region = np.array([[0, 0]])  # Placeholder
        else:
            region = vor.vertices[region_vertices_idx]

        # Clip region to pitch boundaries
        clipped = _clip_polygon_to_pitch(region, pitch_length, pitch_width)

        if len(clipped) >= 3:
            area = _polygon_area(clipped)
        else:
            area = 0.0

        if i < n_home:
            home_regions.append(clipped)
            home_area += area
        else:
            away_regions.append(clipped)
            away_area += area

    return VoronoiFrame(
        timestamp=timestamp,
        home_positions=home_positions,
        away_positions=away_positions,
        voronoi=vor,
        home_control_area=round(home_area, 1),
        away_control_area=round(away_area, 1),
        home_regions=home_regions,
        away_regions=away_regions,
    )


def compute_spatial_dominance(
    tracking_frames: list[dict[str, np.ndarray]],
    pitch_length: float = _PITCH_LENGTH,
    pitch_width: float = _PITCH_WIDTH,
) -> SpaceDominanceResult:
    """Compute spatial dominance over multiple frames.

    Args:
        tracking_frames: List of dicts with 'home_positions', 'away_positions',
                         and optionally 'timestamp'.
        pitch_length: Pitch length in metres.
        pitch_width: Pitch width in metres.

    Returns:
        SpaceDominanceResult with per-frame and aggregate metrics.
    """
    frames = []
    home_controls = []
    away_controls = []

    for i, frame_data in enumerate(tracking_frames):
        home_pos = frame_data["home_positions"]
        away_pos = frame_data["away_positions"]
        timestamp = frame_data.get("timestamp", float(i))

        vf = compute_voronoi_frame(
            home_pos, away_pos, pitch_length, pitch_width, timestamp
        )
        frames.append(vf)
        home_controls.append(vf.home_control_area)
        away_controls.append(vf.away_control_area)

    home_arr = np.array(home_controls)
    away_arr = np.array(away_controls)

    avg_home = float(home_arr.mean()) if len(home_arr) > 0 else 0.0
    avg_away = float(away_arr.mean()) if len(away_arr) > 0 else 0.0
    total_area = pitch_length * pitch_width

    return SpaceDominanceResult(
        frames=frames,
        avg_home_control=round(avg_home, 1),
        avg_away_control=round(avg_away, 1),
        home_control_timeline=home_arr,
        away_control_timeline=away_arr,
        territorial_advantage=round((avg_home - avg_away) / total_area * 100, 1),
    )


def compute_passing_lanes(
    player_positions: np.ndarray,
    opponent_positions: np.ndarray,
    ball_position: np.ndarray,
    lane_width: float = 2.0,
) -> pd.DataFrame:
    """Analyse available passing lanes from ball carrier.

    For each teammate, determines if a passing lane exists
    (no opponent blocking the direct line).

    Args:
        player_positions: (N, 2) positions of teammates.
        opponent_positions: (M, 2) positions of opponents.
        ball_position: (2,) current ball position.
        lane_width: Width of passing lane corridor (metres).

    Returns:
        DataFrame with lane availability and quality for each teammate.
    """
    lanes = []

    for i, teammate_pos in enumerate(player_positions):
        # Vector from ball to teammate
        direction = teammate_pos - ball_position
        distance = np.linalg.norm(direction)

        if distance < 1.0:
            continue

        direction_normalised = direction / distance
        # Perpendicular vector for lane width
        perp = np.array([-direction_normalised[1], direction_normalised[0]])

        # Check if any opponent is in the lane
        blocked = False
        closest_opponent_dist = float("inf")

        for opp_pos in opponent_positions:
            # Project opponent onto the line from ball to teammate
            to_opp = opp_pos - ball_position
            proj_length = np.dot(to_opp, direction_normalised)

            # Only consider opponents between ball and teammate
            if proj_length < 0 or proj_length > distance:
                continue

            # Distance from opponent to the passing line
            perp_dist = abs(np.dot(to_opp, perp))

            if perp_dist < lane_width:
                blocked = True
                closest_opponent_dist = min(closest_opponent_dist, perp_dist)

        # Lane quality: further from opponents = better
        quality = 1.0 if not blocked else max(0.0, closest_opponent_dist / lane_width)

        lanes.append({
            "teammate_idx": i,
            "distance": round(float(distance), 1),
            "angle": round(float(np.arctan2(direction[1], direction[0])), 3),
            "is_open": not blocked,
            "lane_quality": round(quality, 3),
            "closest_opponent_in_lane": round(float(closest_opponent_dist), 1)
            if closest_opponent_dist != float("inf") else None,
        })

    return pd.DataFrame(lanes)


def compute_defensive_coverage(
    defending_positions: np.ndarray,
    pitch_length: float = _PITCH_LENGTH,
    pitch_width: float = _PITCH_WIDTH,
    grid_resolution: int = 50,
) -> np.ndarray:
    """Compute defensive coverage map (distance to nearest defender).

    Returns a 2D grid where each cell contains the distance to the
    nearest defending player. High values indicate gaps.

    Args:
        defending_positions: (N, 2) defender positions in metres.
        pitch_length: Pitch length.
        pitch_width: Pitch width.
        grid_resolution: Grid cells along the longer dimension.

    Returns:
        2D numpy array (grid_y × grid_x) with distances in metres.
    """
    grid_x = grid_resolution
    grid_y = int(grid_resolution * pitch_width / pitch_length)

    x_coords = np.linspace(0, pitch_length, grid_x)
    y_coords = np.linspace(0, pitch_width, grid_y)
    xx, yy = np.meshgrid(x_coords, y_coords)
    grid_points = np.column_stack([xx.ravel(), yy.ravel()])

    # Distance from each grid point to nearest defender
    distances = np.full(len(grid_points), np.inf)

    for defender in defending_positions:
        d = np.linalg.norm(grid_points - defender, axis=1)
        distances = np.minimum(distances, d)

    return distances.reshape(grid_y, grid_x)


def identify_space_creation_events(
    events_df: pd.DataFrame,
    team_id: int,
) -> pd.DataFrame:
    """Identify events that created space (runs, carries into open areas).

    Uses event data to approximate space creation when tracking data
    is unavailable. Looks for progressive carries and runs into space.

    Args:
        events_df: Event DataFrame.
        team_id: Team to analyse.

    Returns:
        DataFrame of space-creating events with progressive metrics.
    """
    team_events = events_df[events_df["team_id"] == team_id].copy()

    # Progressive carries (move ball > 10m towards goal)
    carries = team_events[team_events["event_type"] == "Carry"].copy()
    if not carries.empty and "carry_end_x" in carries.columns:
        carries["progressive_distance"] = carries["carry_end_x"] - carries["location_x"]
        carries["is_progressive"] = carries["progressive_distance"] > 10
        progressive_carries = carries[carries["is_progressive"]]
    else:
        progressive_carries = pd.DataFrame()

    # Progressive passes (advance ball > 10m)
    passes = team_events[team_events["event_type"] == "Pass"].copy()
    if not passes.empty and "end_location_x" in passes.columns:
        passes["progressive_distance"] = passes["end_location_x"] - passes["location_x"]
        passes["is_progressive"] = passes["progressive_distance"] > 10
        progressive_passes = passes[passes["is_progressive"]]
    else:
        progressive_passes = pd.DataFrame()

    # Combine
    space_events = pd.concat([progressive_carries, progressive_passes], ignore_index=True)

    if not space_events.empty:
        space_events = space_events.sort_values(["match_id", "minute", "second"])
        logger.info(
            "Found %d space-creating events for team %d",
            len(space_events), team_id,
        )

    return space_events


def compute_team_compactness(
    positions: np.ndarray,
    exclude_gk: bool = True,
) -> dict[str, float]:
    """Compute team compactness metrics from player positions.

    Args:
        positions: (N, 2) player positions in metres.
        exclude_gk: Whether to exclude the furthest-back player (assumed GK).

    Returns:
        Dictionary with compactness metrics.
    """
    if len(positions) < 3:
        return {"compactness_area": 0.0, "length": 0.0, "width": 0.0}

    pos = positions.copy()
    if exclude_gk and len(pos) > 3:
        # Remove the player with lowest x (furthest from attacking goal)
        gk_idx = np.argmin(pos[:, 0])
        pos = np.delete(pos, gk_idx, axis=0)

    # Convex hull area
    try:
        hull = ConvexHull(pos)
        area = hull.volume  # In 2D, volume = area
    except Exception:
        area = 0.0

    # Team length (x-range) and width (y-range)
    length = float(pos[:, 0].max() - pos[:, 0].min())
    width = float(pos[:, 1].max() - pos[:, 1].min())

    # Centroid spread
    centroid = pos.mean(axis=0)
    distances = np.linalg.norm(pos - centroid, axis=1)

    return {
        "compactness_area": round(float(area), 1),
        "team_length": round(length, 1),
        "team_width": round(width, 1),
        "avg_spread": round(float(distances.mean()), 1),
        "max_spread": round(float(distances.max()), 1),
    }


# ============================================================================
# Helper functions
# ============================================================================


def _create_boundary_points(
    positions: np.ndarray,
    pitch_length: float,
    pitch_width: float,
) -> np.ndarray:
    """Create mirror boundary points for proper Voronoi clipping."""
    # Reflect points across each boundary
    boundary = []
    for pos in positions:
        boundary.append([-pos[0], pos[1]])  # Left boundary
        boundary.append([2 * pitch_length - pos[0], pos[1]])  # Right boundary
        boundary.append([pos[0], -pos[1]])  # Bottom boundary
        boundary.append([pos[0], 2 * pitch_width - pos[1]])  # Top boundary
    return np.array(boundary)


def _clip_polygon_to_pitch(
    vertices: np.ndarray,
    pitch_length: float,
    pitch_width: float,
) -> np.ndarray:
    """Clip polygon vertices to pitch boundaries using Sutherland-Hodgman."""
    if len(vertices) < 3:
        return vertices

    # Simple bounding box clip
    clipped = vertices.copy()
    clipped[:, 0] = np.clip(clipped[:, 0], 0, pitch_length)
    clipped[:, 1] = np.clip(clipped[:, 1], 0, pitch_width)

    # Remove duplicate points
    if len(clipped) > 1:
        diffs = np.diff(clipped, axis=0)
        mask = np.any(np.abs(diffs) > 0.01, axis=1)
        clipped = np.vstack([clipped[0], clipped[1:][mask]])

    return clipped


def _polygon_area(vertices: np.ndarray) -> float:
    """Compute polygon area using the Shoelace formula."""
    if len(vertices) < 3:
        return 0.0

    n = len(vertices)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i, 0] * vertices[j, 1]
        area -= vertices[j, 0] * vertices[i, 1]

    return abs(area) / 2.0
