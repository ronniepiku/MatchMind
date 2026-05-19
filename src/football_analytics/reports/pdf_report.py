"""Automated PDF report generation.

Produces coach-ready PDF reports from analysis outputs using Jinja2 templates
and WeasyPrint for HTML-to-PDF rendering.

Report types:
1. Match Report — Post-match summary with xG, shots, passing, pressing
2. Opponent Scout — Pre-match preparation document
3. Player Profile — Individual performance overview

Usage:
    uv run fb-report --type match --match-id 3869685 --output reports/
    uv run fb-report --type opponent --team-id 771 --season-id 106
    uv run fb-report --type player --player-id 5503 --season-id 106
"""

from __future__ import annotations

import base64
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from football_analytics.config import config

logger = logging.getLogger(__name__)

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "templates"
REPORTS_DIR = config.data_dir / "reports"


def _fig_to_base64(fig: plt.Figure) -> str:
    """Convert a matplotlib figure to a base64-encoded PNG for embedding in HTML."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return f"data:image/png;base64,{encoded}"


def _render_template(template_name: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 template with given context."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template(template_name)
    return template.render(**context)


def _html_to_pdf(html_content: str, output_path: Path) -> Path:
    """Convert HTML string to PDF file using WeasyPrint."""
    try:
        from weasyprint import HTML

        HTML(string=html_content).write_pdf(str(output_path))
        logger.info("PDF report saved: %s", output_path)
        return output_path
    except ImportError:
        # Fallback: save as HTML if WeasyPrint not available
        html_path = output_path.with_suffix(".html")
        html_path.write_text(html_content, encoding="utf-8")
        logger.warning("WeasyPrint not available — saved as HTML: %s", html_path)
        return html_path


# =============================================================================
# REPORT GENERATORS
# =============================================================================


def generate_match_report(
    match_id: int,
    engine: Any | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Generate a post-match PDF report.

    Contents:
    - Match header (teams, score, date)
    - xG summary and timeline
    - Shot map
    - Key stats comparison
    - Notable events and tactical observations
    """
    from sqlalchemy import text

    from football_analytics.db import get_engine as _get_engine

    if engine is None:
        engine = _get_engine()
    if output_dir is None:
        output_dir = REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fetch match info
    with engine.connect() as conn:
        match_info = pd.read_sql(
            text("SELECT * FROM matches WHERE match_id = :mid"),
            conn,
            params={"mid": match_id},
        )
        if match_info.empty:
            raise ValueError(
                f"Match {match_id} not found in database. "
                "Please run the ingestion pipeline first: uv run fb-ingest"
            )

        # Fetch team stats — handle missing view gracefully
        try:
            team_stats = pd.read_sql(
                text("""
                    SELECT * FROM v_team_match_summary
                    WHERE match_id = :mid
                """),
                conn,
                params={"mid": match_id},
            )
        except Exception as e:
            logger.warning("Could not query v_team_match_summary: %s", e)
            team_stats = pd.DataFrame()

        # Fetch shots for shot map
        shots = pd.read_sql(
            text("""
                SELECT e.*, p.player_name
                FROM events e
                LEFT JOIN players p ON e.player_id = p.player_id
                WHERE e.match_id = :mid AND e.event_type = 'Shot'
            """),
            conn,
            params={"mid": match_id},
        )

    # Generate shot map visualisation
    shot_map_b64 = ""
    if not shots.empty:
        try:
            from football_analytics.analysis.visualisations import plot_shot_map

            fig = plot_shot_map(shots, title=f"Shot Map — Match {match_id}")
            shot_map_b64 = _fig_to_base64(fig)
        except Exception as e:
            logger.warning("Could not generate shot map: %s", e)

    # Build context
    match = match_info.iloc[0]
    context = {
        "title": "Match Report",
        "match_date": str(match.get("match_date", "")),
        "match_id": match_id,
        "home_score": match.get("home_score", 0),
        "away_score": match.get("away_score", 0),
        "team_stats": team_stats.to_dict("records") if not team_stats.empty else [],
        "shot_map_img": shot_map_b64,
        "shots_summary": (
            shots.groupby("team_id")
            .agg(
                shots=("event_id", "count"),
                xg=("xg", "sum"),
                goals=("shot_outcome", lambda x: (x == "Goal").sum()),
            )
            .reset_index()
            .to_dict("records")
            if not shots.empty
            else []
        ),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    # Render and save
    html = _render_template("match_report.html", context)
    output_path = output_dir / f"match_report_{match_id}.pdf"
    return _html_to_pdf(html, output_path)


def generate_opponent_report(
    team_id: int,
    season_id: int,
    engine: Any | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Generate an opponent scouting PDF report.

    Contents:
    - Team overview and season stats
    - Attack pattern breakdown
    - Defensive shape analysis
    - Key player threats (top 5 by xG+xA)
    - Tactical recommendations
    """
    from football_analytics.analysis.opponent_profile import build_opponent_report
    from football_analytics.db import get_engine as _get_engine

    if engine is None:
        engine = _get_engine()
    if output_dir is None:
        output_dir = REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    report = build_opponent_report(team_id, season_id, engine)

    # Check if any data was returned
    all_empty = all(
        report[key].empty
        for key in ("attack_patterns", "defensive_shape", "key_players")
    )
    if all_empty:
        raise ValueError(
            f"No data available for team_id={team_id}, season_id={season_id}. "
            "Ensure the data has been ingested for this team/season combination. "
            "Run: uv run fb-ingest"
        )

    context = {
        "title": "Opponent Scouting Report",
        "team_id": team_id,
        "season_id": season_id,
        "attack_patterns": report["attack_patterns"].to_dict("records"),
        "defensive_shape": report["defensive_shape"].to_dict("records"),
        "key_players": report["key_players"].to_dict("records"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    html = _render_template("opponent_report.html", context)
    output_path = output_dir / f"opponent_report_{team_id}_s{season_id}.pdf"
    return _html_to_pdf(html, output_path)


def generate_player_report(
    player_id: int,
    season_id: int,
    engine: Any | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Generate a player performance PDF report.

    Contents:
    - Player header (name, team, position)
    - Season statistics summary
    - Rolling form chart
    - Radar comparison (percentile)
    - Key strengths and areas for development
    """
    from football_analytics.analysis.player_performance import (
        get_player_rolling_form,
        get_player_season_summary,
    )
    from football_analytics.db import get_engine as _get_engine

    if engine is None:
        engine = _get_engine()
    if output_dir is None:
        output_dir = REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = get_player_season_summary(engine, player_id, season_id)
    rolling = get_player_rolling_form(engine, player_id, season_id)

    if summary.empty:
        raise ValueError(
            f"No data available for player_id={player_id}, season_id={season_id}. "
            "Ensure the data has been ingested for this player/season combination. "
            "Run: uv run fb-ingest"
        )

    context = {
        "title": "Player Performance Report",
        "player_id": player_id,
        "season_id": season_id,
        "summary": summary.to_dict("records")[0] if not summary.empty else {},
        "rolling_data": rolling.to_dict("records") if not rolling.empty else [],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    html = _render_template("player_report.html", context)
    output_path = output_dir / f"player_report_{player_id}_s{season_id}.pdf"
    return _html_to_pdf(html, output_path)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main() -> None:
    """CLI entry point for PDF report generation."""
    import argparse

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    parser = argparse.ArgumentParser(description="Generate PDF reports")
    parser.add_argument(
        "--type", choices=["match", "opponent", "player"], required=True
    )
    parser.add_argument("--match-id", type=int, help="Match ID (for match reports)")
    parser.add_argument("--team-id", type=int, help="Team ID (for opponent reports)")
    parser.add_argument("--player-id", type=int, help="Player ID (for player reports)")
    parser.add_argument("--season-id", type=int, default=106, help="Season ID")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else None

    if args.type == "match":
        if not args.match_id:
            parser.error("--match-id required for match reports")
        generate_match_report(args.match_id, output_dir=output_dir)

    elif args.type == "opponent":
        if not args.team_id:
            parser.error("--team-id required for opponent reports")
        generate_opponent_report(args.team_id, args.season_id, output_dir=output_dir)

    elif args.type == "player":
        if not args.player_id:
            parser.error("--player-id required for player reports")
        generate_player_report(args.player_id, args.season_id, output_dir=output_dir)


if __name__ == "__main__":
    main()
