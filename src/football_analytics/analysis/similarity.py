"""Player similarity engine — embedding-based player comparison.

Computes multi-dimensional player profiles and finds similar players
using cosine similarity on normalised feature vectors.

Use cases:
- Recruitment: "Find players similar to X who are younger/cheaper"
- Tactical replacement: "Who in our squad can fill role Y?"
- Benchmarking: "How does this player compare to peers?"

Method:
1. Compute per-90-minute metrics for each player
2. Normalise features to [0, 1] range (min-max within position group)
3. Compute cosine similarity between player vectors
4. Rank by similarity score

Position-aware: Compares players within the same positional group
to avoid nonsensical comparisons (e.g., striker vs goalkeeper).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial.distance import cosine
from sklearn.preprocessing import MinMaxScaler

from football_analytics.db import get_engine

logger = logging.getLogger(__name__)

# Position group mapping (StatsBomb positions → groups)
POSITION_GROUPS: dict[str, str] = {
    "Goalkeeper": "GK",
    "Right Back": "FB",
    "Left Back": "FB",
    "Right Wing Back": "FB",
    "Left Wing Back": "FB",
    "Right Center Back": "CB",
    "Left Center Back": "CB",
    "Center Back": "CB",
    "Right Defensive Midfield": "DM",
    "Left Defensive Midfield": "DM",
    "Center Defensive Midfield": "DM",
    "Right Center Midfield": "CM",
    "Left Center Midfield": "CM",
    "Center Midfield": "CM",
    "Right Attacking Midfield": "AM",
    "Left Attacking Midfield": "AM",
    "Center Attacking Midfield": "AM",
    "Right Wing": "W",
    "Left Wing": "W",
    "Right Center Forward": "FW",
    "Left Center Forward": "FW",
    "Center Forward": "FW",
    "Striker": "FW",
}

# Feature sets by position group (different positions have different key metrics)
FEATURE_SETS: dict[str, list[str]] = {
    "GK": ["saves_per_match", "pass_accuracy", "long_passes_per_match"],
    "CB": [
        "tackles_per_match", "interceptions_per_match", "pressures_per_match",
        "passes_per_match", "pass_accuracy", "aerial_wins_per_match",
    ],
    "FB": [
        "tackles_per_match", "interceptions_per_match", "pressures_per_match",
        "passes_per_match", "key_passes_per_match", "dribbles_per_match",
        "crosses_per_match",
    ],
    "DM": [
        "tackles_per_match", "interceptions_per_match", "pressures_per_match",
        "passes_per_match", "pass_accuracy", "progressive_passes_per_match",
    ],
    "CM": [
        "passes_per_match", "pass_accuracy", "key_passes_per_match",
        "progressive_passes_per_match", "pressures_per_match",
        "dribbles_per_match", "xa_per_match",
    ],
    "AM": [
        "xa_per_match", "xg_per_match", "key_passes_per_match",
        "dribbles_per_match", "shots_per_match", "passes_per_match",
    ],
    "W": [
        "xg_per_match", "xa_per_match", "dribbles_per_match",
        "key_passes_per_match", "shots_per_match", "crosses_per_match",
        "pressures_per_match",
    ],
    "FW": [
        "xg_per_match", "shots_per_match", "xa_per_match",
        "key_passes_per_match", "dribbles_per_match", "pressures_per_match",
        "aerial_wins_per_match",
    ],
}

# Default feature set for unknown positions
DEFAULT_FEATURES = [
    "xg_per_match", "xa_per_match", "passes_per_match", "pass_accuracy",
    "dribbles_per_match", "pressures_per_match", "tackles_per_match",
]


def compute_player_vectors(
    season_id: int,
    engine: Any | None = None,
    min_appearances: int = 3,
) -> pd.DataFrame:
    """Compute per-90 feature vectors for all players in a season.

    Returns a DataFrame with one row per player and normalised features.
    """
    if engine is None:
        engine = get_engine()

    from sqlalchemy import text

    query = text("""
        SELECT
            e.player_id,
            p.player_name,
            e.team_id,
            t.team_name,
            COUNT(DISTINCT e.match_id) AS appearances,
            -- Attacking
            COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0)::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS xg_per_match,
            COALESCE(SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL), 0)::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS xa_per_match,
            COUNT(*) FILTER (WHERE e.event_type = 'Shot')::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS shots_per_match,
            COUNT(*) FILTER (WHERE e.key_pass)::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS key_passes_per_match,
            -- Passing
            COUNT(*) FILTER (WHERE e.event_type = 'Pass')::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS passes_per_match,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL)::FLOAT /
                NULLIF(COUNT(*) FILTER (WHERE e.event_type = 'Pass'), 0) AS pass_accuracy,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_length > 32)::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS long_passes_per_match,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.end_location_x > e.location_x + 10)::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS progressive_passes_per_match,
            -- Dribbling & Carrying
            COUNT(*) FILTER (WHERE e.event_type = 'Dribble' AND e.dribble_outcome = 'Complete')::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS dribbles_per_match,
            -- Defensive
            COUNT(*) FILTER (WHERE e.event_type = 'Pressure')::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS pressures_per_match,
            COUNT(*) FILTER (WHERE e.event_type = 'Tackle')::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS tackles_per_match,
            COUNT(*) FILTER (WHERE e.event_type = 'Interception')::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS interceptions_per_match,
            -- Aerial & Crosses (approximated from available data)
            COUNT(*) FILTER (WHERE e.event_type = 'Duel' AND e.duel_type = 'Aerial Lost')::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS aerial_wins_per_match,
            COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_type = 'Cross')::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS crosses_per_match,
            -- Saves (for GK)
            COUNT(*) FILTER (WHERE e.event_type = 'Goal Keeper')::FLOAT /
                NULLIF(COUNT(DISTINCT e.match_id), 0) AS saves_per_match
        FROM events e
        JOIN players p ON e.player_id = p.player_id
        JOIN teams t ON e.team_id = t.team_id
        JOIN matches m ON e.match_id = m.match_id
        WHERE m.season_id = :season_id
          AND e.player_id IS NOT NULL
        GROUP BY e.player_id, p.player_name, e.team_id, t.team_name
        HAVING COUNT(DISTINCT e.match_id) >= :min_apps
    """)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"season_id": season_id, "min_apps": min_appearances})

    logger.info("Computed vectors for %d players (season %d)", len(df), season_id)
    return df


def find_similar_players(
    target_player_id: int,
    player_vectors: pd.DataFrame,
    position_group: str | None = None,
    top_n: int = 10,
    features: list[str] | None = None,
) -> pd.DataFrame:
    """Find the most similar players to a target player.

    Uses cosine similarity on normalised feature vectors within
    the same position group for meaningful comparisons.

    Args:
        target_player_id: The player to find similar players for.
        player_vectors: Full DataFrame from compute_player_vectors.
        position_group: Position group to compare within (e.g., "FW", "CM").
                       If None, uses DEFAULT_FEATURES and compares all.
        top_n: Number of similar players to return.
        features: Custom feature list (overrides position-based defaults).

    Returns:
        DataFrame with similar players ranked by similarity score [0, 1].
    """
    if target_player_id not in player_vectors["player_id"].values:
        raise ValueError(f"Player {target_player_id} not found in vectors")

    # Select feature set
    if features is not None:
        feature_cols = features
    elif position_group and position_group in FEATURE_SETS:
        feature_cols = FEATURE_SETS[position_group]
    else:
        feature_cols = DEFAULT_FEATURES

    # Filter to available columns
    feature_cols = [c for c in feature_cols if c in player_vectors.columns]
    if len(feature_cols) < 2:
        raise ValueError("Insufficient features available for comparison")

    # Extract feature matrix
    feature_matrix = player_vectors[feature_cols].fillna(0).values

    # Normalise features (min-max within the comparison group)
    scaler = MinMaxScaler()
    normalised = scaler.fit_transform(feature_matrix)

    # Get target player's vector
    target_idx = player_vectors[player_vectors["player_id"] == target_player_id].index[0]
    target_vector = normalised[target_idx]

    # Compute cosine similarity to all other players
    similarities = []
    for i in range(len(normalised)):
        if i == target_idx:
            continue
        # Cosine similarity = 1 - cosine distance
        sim = 1 - cosine(target_vector, normalised[i])
        similarities.append((i, sim))

    # Sort by similarity (descending)
    similarities.sort(key=lambda x: x[1], reverse=True)

    # Build result DataFrame
    results = []
    for idx, sim_score in similarities[:top_n]:
        row = player_vectors.iloc[idx]
        results.append({
            "player_id": int(row["player_id"]),
            "player_name": row["player_name"],
            "team_name": row["team_name"],
            "similarity": round(sim_score, 4),
            "appearances": int(row["appearances"]),
        })

    result_df = pd.DataFrame(results)
    logger.info(
        "Found %d similar players to %s (position=%s)",
        len(result_df),
        player_vectors[player_vectors["player_id"] == target_player_id]["player_name"].iloc[0],
        position_group or "all",
    )
    return result_df


def build_similarity_matrix(
    player_vectors: pd.DataFrame,
    features: list[str] | None = None,
) -> pd.DataFrame:
    """Build a full player-vs-player similarity matrix.

    Useful for clustering analysis and network visualisation.

    Returns:
        Square DataFrame (n_players × n_players) with similarity scores.
    """
    feature_cols = features or DEFAULT_FEATURES
    feature_cols = [c for c in feature_cols if c in player_vectors.columns]

    feature_matrix = player_vectors[feature_cols].fillna(0).values
    scaler = MinMaxScaler()
    normalised = scaler.fit_transform(feature_matrix)

    n = len(normalised)
    sim_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(i, n):
            if i == j:
                sim_matrix[i, j] = 1.0
            else:
                sim = 1 - cosine(normalised[i], normalised[j])
                sim_matrix[i, j] = sim
                sim_matrix[j, i] = sim

    player_names = player_vectors["player_name"].values
    return pd.DataFrame(sim_matrix, index=player_names, columns=player_names)


def recommend_replacements(
    target_player_id: int,
    player_vectors: pd.DataFrame,
    position_group: str,
    exclude_team_id: int | None = None,
    min_similarity: float = 0.75,
    top_n: int = 5,
) -> pd.DataFrame:
    """Recommend transfer/replacement targets for a specific player.

    Filters out players from the same team and applies a minimum
    similarity threshold.

    Args:
        target_player_id: Player to find replacements for.
        player_vectors: Full player vector DataFrame.
        position_group: Position to compare within.
        exclude_team_id: Exclude players from this team (the player's own team).
        min_similarity: Minimum similarity score to include.
        top_n: Number of recommendations.

    Returns:
        DataFrame of recommended players with similarity scores.
    """
    # Filter out target player's team if specified
    comparison_df = player_vectors.copy()
    if exclude_team_id is not None:
        comparison_df = comparison_df[comparison_df["team_id"] != exclude_team_id]

    # Ensure target player is still in the DataFrame for comparison
    target_row = player_vectors[player_vectors["player_id"] == target_player_id]
    if target_row.empty:
        raise ValueError(f"Player {target_player_id} not found")

    comparison_df = pd.concat([target_row, comparison_df]).drop_duplicates(subset=["player_id"])

    similar = find_similar_players(
        target_player_id=target_player_id,
        player_vectors=comparison_df,
        position_group=position_group,
        top_n=top_n * 2,  # Get extra to filter
    )

    # Apply minimum similarity threshold
    similar = similar[similar["similarity"] >= min_similarity].head(top_n)

    return similar
