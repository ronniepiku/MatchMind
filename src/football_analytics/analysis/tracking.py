"""Tracking data integration module.

Provides interfaces and utilities for integrating positional tracking data
(e.g., from Second Spectrum, SkillCorner, Metrica Sports open data) with
StatsBomb event data.

Tracking data enables:
- Off-ball player movement analysis
- Space control / Pitch control models
- Physical metrics (speed, distance, acceleration)
- Defensive line height and compactness
- Press trigger identification

This module provides:
1. Data format adapters (Metrica, EPTS, custom CSV)
2. Event-tracking synchronisation
3. Space control calculations
4. Physical performance metrics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Standard pitch dimensions (metres) — tracking data typically uses metres
PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0

# StatsBomb pitch dimensions (for coordinate conversion)
SB_PITCH_LENGTH = 120.0
SB_PITCH_WIDTH = 80.0


@dataclass
class TrackingFrame:
    """A single frame of tracking data (typically 25fps)."""

    frame_id: int
    timestamp: float  # seconds from kick-off
    period: int
    ball_x: float
    ball_y: float
    home_positions: np.ndarray  # shape (n_players, 2)
    away_positions: np.ndarray  # shape (n_players, 2)
    home_velocities: np.ndarray | None = None  # shape (n_players, 2)
    away_velocities: np.ndarray | None = None


# =============================================================================
# DATA FORMAT ADAPTERS
# =============================================================================


def load_metrica_tracking(
    home_path: str,
    away_path: str,
) -> pd.DataFrame:
    """Load Metrica Sports open tracking data format.

    Metrica provides free sample data at:
    https://github.com/metrica-sports/sample-data

    Format: CSV with columns for each player's x, y coordinates per frame.

    Args:
        home_path: Path to home team tracking CSV.
        away_path: Path to away team tracking CSV.

    Returns:
        Combined DataFrame with standardised column names.
    """
    home_df = pd.read_csv(home_path, skiprows=2)
    away_df = pd.read_csv(away_path, skiprows=2)

    # Standardise column naming
    home_df.columns = [c.strip() for c in home_df.columns]
    away_df.columns = [c.strip() for c in away_df.columns]

    logger.info(
        "Loaded Metrica tracking: %d home frames, %d away frames",
        len(home_df), len(away_df),
    )
    return home_df, away_df


def load_epts_tracking(filepath: str) -> pd.DataFrame:
    """Load EPTS (Electronic Performance and Tracking Systems) format.

    EPTS is the FIFA-standard format used in professional football.
    Data comes as position records at 25Hz.

    Args:
        filepath: Path to EPTS data file.

    Returns:
        DataFrame with columns: frame_id, timestamp, player_id, x, y, speed.
    """
    # EPTS typically comes as fixed-width or CSV with specific structure
    df = pd.read_csv(filepath)
    required_cols = {"frame_id", "timestamp", "player_id", "x", "y"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"EPTS file must contain columns: {required_cols}")

    logger.info("Loaded EPTS tracking: %d records", len(df))
    return df


def convert_coordinates_sb_to_tracking(
    x: float | np.ndarray,
    y: float | np.ndarray,
) -> tuple[float | np.ndarray, float | np.ndarray]:
    """Convert StatsBomb coordinates (120×80) to tracking coordinates (105×68 metres)."""
    tracking_x = x * (PITCH_LENGTH / SB_PITCH_LENGTH)
    tracking_y = y * (PITCH_WIDTH / SB_PITCH_WIDTH)
    return tracking_x, tracking_y


def convert_coordinates_tracking_to_sb(
    x: float | np.ndarray,
    y: float | np.ndarray,
) -> tuple[float | np.ndarray, float | np.ndarray]:
    """Convert tracking coordinates (metres) to StatsBomb coordinates (120×80)."""
    sb_x = x * (SB_PITCH_LENGTH / PITCH_LENGTH)
    sb_y = y * (SB_PITCH_WIDTH / PITCH_WIDTH)
    return sb_x, sb_y


# =============================================================================
# EVENT-TRACKING SYNCHRONISATION
# =============================================================================


def sync_events_to_tracking(
    events_df: pd.DataFrame,
    tracking_df: pd.DataFrame,
    fps: int = 25,
    time_tolerance: float = 0.5,
) -> pd.DataFrame:
    """Synchronise StatsBomb events to tracking data frames.

    Maps each event to the nearest tracking frame based on timestamp matching.

    Args:
        events_df: StatsBomb events with 'minute', 'second' columns.
        tracking_df: Tracking data with 'timestamp' column (seconds from kick-off).
        fps: Tracking data frame rate (typically 25).
        time_tolerance: Max seconds between event and matched frame.

    Returns:
        Events DataFrame with added 'tracking_frame_id' column.
    """
    # Convert event timestamps to seconds from period start
    events_df = events_df.copy()
    events_df["event_seconds"] = events_df["minute"] * 60 + events_df["second"].fillna(0)

    # Match each event to nearest tracking frame
    tracking_times = tracking_df["timestamp"].values

    def _find_nearest_frame(event_seconds: float) -> int | None:
        """Find the tracking frame closest to the event timestamp."""
        diffs = np.abs(tracking_times - event_seconds)
        min_idx = diffs.argmin()
        if diffs[min_idx] <= time_tolerance:
            return int(tracking_df.iloc[min_idx]["frame_id"])
        return None

    events_df["tracking_frame_id"] = events_df["event_seconds"].apply(_find_nearest_frame)

    matched = events_df["tracking_frame_id"].notna().sum()
    logger.info(
        "Synced %d/%d events to tracking frames (%.1f%% matched)",
        matched, len(events_df), matched / len(events_df) * 100,
    )
    return events_df


# =============================================================================
# SPACE CONTROL / PITCH CONTROL
# =============================================================================


def calculate_pitch_control(
    ball_pos: np.ndarray,
    home_positions: np.ndarray,
    away_positions: np.ndarray,
    home_velocities: np.ndarray | None = None,
    away_velocities: np.ndarray | None = None,
    grid_resolution: float = 1.0,
) -> np.ndarray:
    """Calculate pitch control using a simplified influence model.

    Each player exerts influence proportional to 1/distance² from each point,
    modified by their velocity (can reach points in their movement direction faster).

    This is a simplified version of the Fernandez & Bornn (2018) model.

    Args:
        ball_pos: Ball position [x, y].
        home_positions: Home team player positions, shape (N, 2).
        away_positions: Away team player positions, shape (M, 2).
        home_velocities: Optional velocity vectors for home players.
        away_velocities: Optional velocity vectors for away players.
        grid_resolution: Grid cell size in metres (lower = higher resolution).

    Returns:
        2D array of pitch control values [-1, 1] where:
        +1 = full home control, -1 = full away control, 0 = contested.
    """
    # Create pitch grid
    x_grid = np.arange(0, PITCH_LENGTH, grid_resolution)
    y_grid = np.arange(0, PITCH_WIDTH, grid_resolution)
    xx, yy = np.meshgrid(x_grid, y_grid)
    grid_points = np.stack([xx.ravel(), yy.ravel()], axis=1)  # (G, 2)

    def _team_influence(positions: np.ndarray, velocities: np.ndarray | None) -> np.ndarray:
        """Calculate total team influence at each grid point."""
        # Distances from each player to each grid point
        # positions: (N, 2), grid_points: (G, 2) → distances: (N, G)
        diffs = grid_points[np.newaxis, :, :] - positions[:, np.newaxis, :]  # (N, G, 2)
        distances = np.linalg.norm(diffs, axis=2)  # (N, G)

        # Influence: inverse-square with minimum distance clamp
        influence = 1.0 / (distances**2 + 1.0)

        # Velocity adjustment: players moving towards a point have more influence
        if velocities is not None:
            # Dot product of velocity with direction to grid point
            directions = diffs / (distances[:, :, np.newaxis] + 1e-8)
            vel_alignment = np.einsum("ij,ikj->ik", velocities, directions)
            # Boost influence for positive alignment
            influence *= (1.0 + np.clip(vel_alignment, 0, 2))

        return influence.sum(axis=0)  # Sum across players → (G,)

    home_influence = _team_influence(home_positions, home_velocities)
    away_influence = _team_influence(away_positions, away_velocities)

    # Normalise to [-1, 1]
    total = home_influence + away_influence + 1e-8
    control = (home_influence - away_influence) / total

    return control.reshape(xx.shape)


# =============================================================================
# PHYSICAL PERFORMANCE METRICS
# =============================================================================


def calculate_physical_metrics(
    player_tracking: pd.DataFrame,
    fps: int = 25,
) -> dict[str, float]:
    """Calculate physical performance metrics for a player in a match.

    Args:
        player_tracking: DataFrame with columns: timestamp, x, y for one player.
        fps: Frame rate of tracking data.

    Returns:
        Dict with: total_distance, max_speed, avg_speed, sprints, high_intensity_distance.
    """
    dt = 1.0 / fps  # Time between frames

    # Calculate velocities
    dx = np.diff(player_tracking["x"].values)
    dy = np.diff(player_tracking["y"].values)
    speeds = np.sqrt(dx**2 + dy**2) / dt  # m/s

    # Distance = sum of displacements
    total_distance = np.sum(np.sqrt(dx**2 + dy**2))

    # Speed thresholds (m/s)
    SPRINT_THRESHOLD = 7.0      # > 25.2 km/h
    HIGH_INTENSITY = 5.5        # > 19.8 km/h

    sprints = np.sum(speeds > SPRINT_THRESHOLD)
    high_intensity_distance = np.sum(
        np.sqrt(dx**2 + dy**2)[speeds[:-1] > HIGH_INTENSITY] if len(speeds) > 1 else 0
    )

    return {
        "total_distance_m": round(total_distance, 1),
        "total_distance_km": round(total_distance / 1000, 2),
        "max_speed_ms": round(float(np.max(speeds)) if len(speeds) > 0 else 0, 2),
        "max_speed_kmh": round(float(np.max(speeds)) * 3.6 if len(speeds) > 0 else 0, 1),
        "avg_speed_kmh": round(float(np.mean(speeds)) * 3.6 if len(speeds) > 0 else 0, 1),
        "sprint_count": int(sprints),
        "high_intensity_distance_m": round(float(high_intensity_distance), 1),
    }


def calculate_team_shape(
    positions: np.ndarray,
) -> dict[str, float]:
    """Calculate team shape metrics from player positions.

    Metrics:
    - Width: lateral spread of the team
    - Length: longitudinal spread (depth)
    - Compactness: area of convex hull
    - Defensive line height: average x of back 4

    Args:
        positions: Player positions, shape (N, 2) where N is typically 10 (outfield).

    Returns:
        Dict with shape metrics.
    """
    if len(positions) < 3:
        return {"width": 0, "length": 0, "compactness": 0, "def_line_height": 0}

    x_coords = positions[:, 0]
    y_coords = positions[:, 1]

    # Sort by x to find defensive line (lowest x = deepest)
    sorted_x = np.sort(x_coords)

    return {
        "width": float(np.ptp(y_coords)),  # max - min of y
        "length": float(np.ptp(x_coords)),  # max - min of x
        "centroid_x": float(np.mean(x_coords)),
        "centroid_y": float(np.mean(y_coords)),
        "defensive_line_height": float(np.mean(sorted_x[:4])),  # Back 4 average
        "compactness": float(np.std(x_coords) * np.std(y_coords)),  # Spread measure
    }
