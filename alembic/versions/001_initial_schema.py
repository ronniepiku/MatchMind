"""Initial schema — all tables from schema.sql plus v0.5.0 additions.

Revision ID: 001
Revises:
Create Date: 2026-06-03
"""

from pathlib import Path

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply full schema from schema.sql plus v0.5.0 additions."""
    # Execute the base schema.sql
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "football_analytics"
        / "db"
        / "schema.sql"
    )
    if schema_path.exists():
        sql = schema_path.read_text(encoding="utf-8")
        op.execute(sa.text(sql))

    # v0.5.0 additions: competition_registry, matchday_events, data_quality_log
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS competition_registry (
            id                  SERIAL PRIMARY KEY,
            competition_id      INTEGER NOT NULL,
            season_id           INTEGER NOT NULL,
            competition_name    VARCHAR(200) NOT NULL,
            country             VARCHAR(100) DEFAULT '',
            is_active           BOOLEAN DEFAULT TRUE,
            priority            SMALLINT DEFAULT 1,
            last_sync           TIMESTAMP,
            matches_synced      INTEGER DEFAULT 0,
            total_matches       INTEGER DEFAULT 0,
            created_at          TIMESTAMP DEFAULT NOW(),
            updated_at          TIMESTAMP DEFAULT NOW(),
            UNIQUE (competition_id, season_id)
        );

        CREATE INDEX IF NOT EXISTS idx_registry_active
            ON competition_registry (is_active, priority);
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS matchday_events (
            id                  SERIAL PRIMARY KEY,
            fixture_id          INTEGER REFERENCES fixtures(fixture_id),
            event_type          VARCHAR(50) NOT NULL,
            event_data          JSONB NOT NULL DEFAULT '{}',
            created_at          TIMESTAMP DEFAULT NOW(),
            created_by          VARCHAR(100) DEFAULT 'system'
        );

        CREATE INDEX IF NOT EXISTS idx_matchday_events_fixture
            ON matchday_events (fixture_id, event_type);
    """))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS data_quality_log (
            id                  SERIAL PRIMARY KEY,
            source              VARCHAR(100) NOT NULL,
            check_name          VARCHAR(200) NOT NULL,
            severity            VARCHAR(20) NOT NULL DEFAULT 'warning',
            details             JSONB NOT NULL DEFAULT '{}',
            record_count        INTEGER,
            failed_count        INTEGER,
            pass_rate           REAL,
            created_at          TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_quality_log_source
            ON data_quality_log (source, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_quality_log_severity
            ON data_quality_log (severity, created_at DESC);
    """))

    # Cache metadata table for HTTP-level caching
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cache_metadata (
            cache_key           VARCHAR(200) PRIMARY KEY,
            endpoint            VARCHAR(200) NOT NULL,
            params_hash         VARCHAR(64) NOT NULL,
            created_at          TIMESTAMP DEFAULT NOW(),
            expires_at          TIMESTAMP NOT NULL,
            hit_count           INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_cache_metadata_expiry
            ON cache_metadata (expires_at);
    """))


def downgrade() -> None:
    """Drop v0.5.0 additions (does not drop base schema to avoid data loss)."""
    op.execute(sa.text("DROP TABLE IF EXISTS cache_metadata CASCADE;"))
    op.execute(sa.text("DROP TABLE IF EXISTS data_quality_log CASCADE;"))
    op.execute(sa.text("DROP TABLE IF EXISTS matchday_events CASCADE;"))
    op.execute(sa.text("DROP TABLE IF EXISTS competition_registry CASCADE;"))
