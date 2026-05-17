"""Visualisation module — static and interactive football plots.

Uses mplsoccer for pitch-based visualisations and Plotly for interactive charts.
All functions return figure objects for embedding in notebooks or dashboards.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from matplotlib.figure import Figure
from mplsoccer import Pitch, VerticalPitch


# =============================================================================
# STATIC VISUALISATIONS (Matplotlib / mplsoccer)
# =============================================================================


def plot_shot_map(
    shots_df: pd.DataFrame,
    title: str = "Shot Map",
    team_color: str = "#1f77b4",
) -> Figure:
    """Plot shots on a vertical half-pitch, sized by xG.

    Args:
        shots_df: Must contain columns: location_x, location_y, xg, shot_outcome.
        title: Plot title.
        team_color: Base colour for non-goal shots.

    Returns:
        Matplotlib Figure object.

    Football insight: Visualises shot quality distribution — are shots
    coming from dangerous positions or long-range efforts?
    """
    pitch = VerticalPitch(half=True, pitch_type="statsbomb", line_color="#c7d5cc")
    fig, ax = pitch.draw(figsize=(8, 6))

    # Goals in red, other shots in team colour
    goals = shots_df[shots_df["shot_outcome"] == "Goal"]
    non_goals = shots_df[shots_df["shot_outcome"] != "Goal"]

    # Size proportional to xG (scaled for visibility)
    pitch.scatter(
        non_goals["location_x"], non_goals["location_y"],
        s=non_goals["xg"].fillna(0) * 500 + 30,
        c=team_color, alpha=0.6, edgecolors="black", linewidth=0.5,
        ax=ax, zorder=2,
    )
    pitch.scatter(
        goals["location_x"], goals["location_y"],
        s=goals["xg"].fillna(0) * 500 + 30,
        c="red", alpha=0.9, edgecolors="black", linewidth=1,
        ax=ax, zorder=3, marker="*",
    )

    ax.set_title(title, fontsize=14, fontweight="bold", pad=10)
    fig.text(0.5, 0.02, "Circle size = xG | Stars = Goals", ha="center", fontsize=9, alpha=0.7)
    plt.tight_layout()
    return fig


def plot_passing_network(
    pass_df: pd.DataFrame,
    avg_positions: pd.DataFrame,
    title: str = "Passing Network",
) -> Figure:
    """Draw a passing network showing player positions and connection strength.

    Args:
        pass_df: Columns: passer_id, receiver_id, pass_count.
        avg_positions: Columns: player_id, avg_x, avg_y, player_name, passes_made.

    Football insight: Reveals team structure, key passing hubs, and
    potential isolation of wide players.
    """
    pitch = Pitch(pitch_type="statsbomb", line_color="#c7d5cc")
    fig, ax = pitch.draw(figsize=(12, 8))

    # Normalise line width by pass count
    max_passes = pass_df["pass_count"].max() if not pass_df.empty else 1

    for _, row in pass_df.iterrows():
        passer_pos = avg_positions[avg_positions["player_id"] == row["passer_id"]]
        receiver_pos = avg_positions[avg_positions["player_id"] == row["receiver_id"]]
        if passer_pos.empty or receiver_pos.empty:
            continue

        line_width = (row["pass_count"] / max_passes) * 6 + 0.5
        alpha = min(row["pass_count"] / max_passes + 0.3, 1.0)
        ax.plot(
            [passer_pos["avg_x"].iloc[0], receiver_pos["avg_x"].iloc[0]],
            [passer_pos["avg_y"].iloc[0], receiver_pos["avg_y"].iloc[0]],
            color="#2196F3", linewidth=line_width, alpha=alpha, zorder=1,
        )

    # Plot nodes (player positions)
    node_size = avg_positions["passes_made"] / avg_positions["passes_made"].max() * 400 + 100
    pitch.scatter(
        avg_positions["avg_x"], avg_positions["avg_y"],
        s=node_size, c="#FF5722", edgecolors="black", linewidth=1.5,
        ax=ax, zorder=2,
    )

    # Labels
    for _, row in avg_positions.iterrows():
        name_parts = row["player_name"].split()
        label = name_parts[-1] if name_parts else ""
        ax.annotate(
            label, (row["avg_x"], row["avg_y"]),
            textcoords="offset points", xytext=(0, 10),
            ha="center", fontsize=8, fontweight="bold",
        )

    ax.set_title(title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_pressure_heatmap(
    pressures_df: pd.DataFrame,
    title: str = "Pressing Heatmap",
) -> Figure:
    """Kernel density heatmap of pressing actions.

    Football insight: Shows where the team applies the press — are they
    pressing high or sitting deep?
    """
    pitch = Pitch(pitch_type="statsbomb", line_color="#c7d5cc")
    fig, ax = pitch.draw(figsize=(12, 8))

    if not pressures_df.empty:
        pitch.kdeplot(
            pressures_df["location_x"], pressures_df["location_y"],
            ax=ax, cmap="YlOrRd", fill=True, levels=50, alpha=0.7,
        )

    ax.set_title(title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    return fig


# =============================================================================
# INTERACTIVE VISUALISATIONS (Plotly)
# =============================================================================


def plot_xg_timeline(
    shots_df: pd.DataFrame,
    home_team: str,
    away_team: str,
) -> go.Figure:
    """Interactive cumulative xG race chart.

    Football insight: Shows match momentum — which team was creating
    better chances and when. Key for post-match debrief.
    """
    fig = go.Figure()

    for team_name, color in [(home_team, "#1f77b4"), (away_team, "#ff7f0e")]:
        team_shots = shots_df[shots_df["team_name"] == team_name].sort_values("minute")
        if team_shots.empty:
            continue

        cumulative_xg = team_shots["xg"].cumsum()

        # Add start point at 0
        minutes = [0] + team_shots["minute"].tolist()
        xg_values = [0] + cumulative_xg.tolist()

        fig.add_trace(go.Scatter(
            x=minutes,
            y=xg_values,
            mode="lines+markers",
            name=team_name,
            line=dict(color=color, width=2),
            marker=dict(size=6),
            hovertemplate="Min %{x}: xG = %{y:.2f}<extra></extra>",
        ))

    fig.update_layout(
        title="Cumulative xG Timeline",
        xaxis_title="Minute",
        yaxis_title="Cumulative xG",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
    )
    return fig


def plot_player_radar(
    percentiles: dict[str, float],
    player_name: str,
) -> go.Figure:
    """Interactive radar chart for player percentile profile.

    Football insight: At-a-glance multi-dimensional player comparison
    for recruitment shortlisting and tactical fit assessment.
    """
    categories = list(percentiles.keys())
    values = list(percentiles.values())

    # Close the polygon
    categories += [categories[0]]
    values += [values[0]]

    # Clean category labels
    labels = [c.replace("_per_match", "").replace("_", " ").title() for c in categories]

    fig = go.Figure(data=go.Scatterpolar(
        r=values,
        theta=labels,
        fill="toself",
        fillcolor="rgba(31, 119, 180, 0.3)",
        line=dict(color="#1f77b4", width=2),
        name=player_name,
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100]),
        ),
        title=f"{player_name} — Percentile Radar",
        template="plotly_white",
    )
    return fig


def plot_team_trend(
    team_summary_df: pd.DataFrame,
    metric: str = "total_xg",
    title: str | None = None,
) -> go.Figure:
    """Line chart showing team metric evolution over the season.

    Football insight: Identify performance trends, dips after key injuries,
    or tactical changes reflected in metrics.
    """
    fig = px.line(
        team_summary_df.sort_values("match_date"),
        x="match_date",
        y=metric,
        title=title or f"Team {metric.replace('_', ' ').title()} Over Season",
        markers=True,
        template="plotly_white",
    )
    fig.update_traces(line=dict(width=2))
    fig.update_layout(xaxis_title="Match Date", yaxis_title=metric.replace("_", " ").title())
    return fig
