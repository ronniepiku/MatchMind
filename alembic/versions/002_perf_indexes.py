"""Add performance indexes for dashboard hot paths.

Revision ID: 002_perf_indexes
Revises: 001_initial
Create Date: 2026-06-09
"""

import sqlalchemy as sa

from alembic import op

revision = "002_perf_indexes"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add composite indexes for dashboard query hot paths."""
    # Speeds up: scorecard, possession profile, opponent report queries
    # that filter matches by (season_id + team)
    op.execute(
        sa.text("""
        CREATE INDEX IF NOT EXISTS idx_matches_season_home
            ON matches (season_id, home_team_id);

        CREATE INDEX IF NOT EXISTS idx_matches_season_away
            ON matches (season_id, away_team_id);

        -- Covers play_pattern filtering for set-piece queries
        CREATE INDEX IF NOT EXISTS idx_events_play_pattern
            ON events (play_pattern, team_id)
            WHERE play_pattern IN ('From Corner', 'From Free Kick', 'From Throw In');

        -- Covers team+event_type for defensive shape aggregations
        CREATE INDEX IF NOT EXISTS idx_events_team_type_loc
            ON events (team_id, event_type, location_x)
            WHERE event_type IN ('Pressure', 'Tackle', 'Interception', 'Block');
    """)
    )


def downgrade() -> None:
    """Remove performance indexes."""
    op.execute(sa.text("DROP INDEX IF EXISTS idx_matches_season_home;"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_matches_season_away;"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_events_play_pattern;"))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_events_team_type_loc;"))
