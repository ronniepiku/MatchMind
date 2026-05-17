-- ============================================================================
-- Football Analytics — PostgreSQL Schema
-- StatsBomb open-data relational model with performance indexes
-- ============================================================================

-- Enable extensions for advanced features
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- fuzzy text search on player names

-- ============================================================================
-- COMPETITIONS & SEASONS
-- ============================================================================
CREATE TABLE IF NOT EXISTS competitions (
    competition_id   INTEGER PRIMARY KEY,
    competition_name VARCHAR(200) NOT NULL,
    country_name     VARCHAR(100),
    season_id        INTEGER NOT NULL,
    season_name      VARCHAR(50) NOT NULL,
    match_updated    TIMESTAMP,
    match_available  TIMESTAMP,
    UNIQUE (competition_id, season_id)
);

-- ============================================================================
-- TEAMS
-- ============================================================================
CREATE TABLE IF NOT EXISTS teams (
    team_id   INTEGER PRIMARY KEY,
    team_name VARCHAR(200) NOT NULL,
    country   VARCHAR(100)
);

-- ============================================================================
-- PLAYERS
-- ============================================================================
CREATE TABLE IF NOT EXISTS players (
    player_id   INTEGER PRIMARY KEY,
    player_name VARCHAR(200) NOT NULL,
    nickname    VARCHAR(200),
    country     VARCHAR(100)
);

-- ============================================================================
-- MATCHES
-- ============================================================================
CREATE TABLE IF NOT EXISTS matches (
    match_id         INTEGER PRIMARY KEY,
    competition_id   INTEGER NOT NULL REFERENCES competitions(competition_id),
    season_id        INTEGER NOT NULL,
    match_date       DATE NOT NULL,
    kick_off         TIME,
    home_team_id     INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id     INTEGER NOT NULL REFERENCES teams(team_id),
    home_score       SMALLINT,
    away_score       SMALLINT,
    match_week       SMALLINT,
    stadium          VARCHAR(200),
    referee          VARCHAR(200),
    competition_stage VARCHAR(100)
);

-- ============================================================================
-- LINEUPS (match-level squads)
-- ============================================================================
CREATE TABLE IF NOT EXISTS lineups (
    id              SERIAL PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(match_id),
    team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    jersey_number   SMALLINT,
    position        VARCHAR(50),
    is_starter      BOOLEAN DEFAULT FALSE,
    minutes_played  SMALLINT,
    UNIQUE (match_id, team_id, player_id)
);

-- ============================================================================
-- EVENTS (core event-level table — denormalized for query speed)
-- ============================================================================
CREATE TABLE IF NOT EXISTS events (
    event_id         UUID PRIMARY KEY,
    match_id         INTEGER NOT NULL REFERENCES matches(match_id),
    team_id          INTEGER NOT NULL REFERENCES teams(team_id),
    player_id        INTEGER REFERENCES players(player_id),
    event_type       VARCHAR(50) NOT NULL,   -- Pass, Shot, Carry, Pressure, etc.
    period           SMALLINT NOT NULL,
    timestamp        TIME NOT NULL,
    minute           SMALLINT NOT NULL,
    second           SMALLINT,
    possession       INTEGER,
    possession_team_id INTEGER REFERENCES teams(team_id),
    play_pattern     VARCHAR(50),
    location_x       REAL,
    location_y       REAL,
    end_location_x   REAL,
    end_location_y   REAL,
    duration         REAL,
    under_pressure   BOOLEAN DEFAULT FALSE,
    -- Shot-specific
    xg               REAL,
    shot_outcome     VARCHAR(50),
    shot_technique   VARCHAR(50),
    shot_body_part   VARCHAR(50),
    -- Pass-specific
    pass_length      REAL,
    pass_angle       REAL,
    pass_height      VARCHAR(30),
    pass_outcome     VARCHAR(50),
    pass_recipient_id INTEGER REFERENCES players(player_id),
    pass_type        VARCHAR(50),
    key_pass         BOOLEAN DEFAULT FALSE,
    assist           BOOLEAN DEFAULT FALSE,
    xa               REAL,
    -- Carry-specific
    carry_end_x      REAL,
    carry_end_y      REAL,
    -- Duel-specific
    duel_type        VARCHAR(50),
    duel_outcome     VARCHAR(50),
    -- Dribble-specific
    dribble_outcome  VARCHAR(50),
    -- Pressure/defensive
    counterpress     BOOLEAN DEFAULT FALSE,
    -- Metadata
    related_events   UUID[],
    raw_json         JSONB
);

-- ============================================================================
-- PERFORMANCE INDEXES
-- Rationale: These indexes accelerate the most common analytical queries.
-- ============================================================================

-- Fast event filtering by match + type (opponent profiling, match reports)
CREATE INDEX IF NOT EXISTS idx_events_match_type
    ON events (match_id, event_type);

-- Player-level aggregations (performance summaries)
CREATE INDEX IF NOT EXISTS idx_events_player
    ON events (player_id, event_type);

-- Team-level aggregations
CREATE INDEX IF NOT EXISTS idx_events_team
    ON events (team_id, event_type);

-- Temporal queries (time-series, momentum analysis)
CREATE INDEX IF NOT EXISTS idx_events_match_minute
    ON events (match_id, minute);

-- Spatial queries (zone-based analysis like shot maps)
CREATE INDEX IF NOT EXISTS idx_events_location
    ON events (event_type, location_x, location_y)
    WHERE location_x IS NOT NULL;

-- xG-specific queries (shot analysis, model evaluation)
CREATE INDEX IF NOT EXISTS idx_events_xg
    ON events (xg)
    WHERE xg IS NOT NULL;

-- Possession-chain analysis
CREATE INDEX IF NOT EXISTS idx_events_possession
    ON events (match_id, possession);

-- Match schedule lookups
CREATE INDEX IF NOT EXISTS idx_matches_competition
    ON matches (competition_id, season_id, match_date);

-- Lineup lookups
CREATE INDEX IF NOT EXISTS idx_lineups_match_team
    ON lineups (match_id, team_id);

-- ============================================================================
-- VIEWS: Pre-built analytical summaries
-- ============================================================================

-- Player match summary (aggregated per match)
CREATE OR REPLACE VIEW v_player_match_summary AS
SELECT
    e.match_id,
    e.player_id,
    p.player_name,
    e.team_id,
    t.team_name,
    COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS passes_completed,
    COUNT(*) FILTER (WHERE e.event_type = 'Pass') AS passes_attempted,
    COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots,
    SUM(e.xg) FILTER (WHERE e.event_type = 'Shot') AS total_xg,
    COUNT(*) FILTER (WHERE e.event_type = 'Shot' AND e.shot_outcome = 'Goal') AS goals,
    COUNT(*) FILTER (WHERE e.key_pass) AS key_passes,
    SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL) AS total_xa,
    COUNT(*) FILTER (WHERE e.event_type = 'Dribble' AND e.dribble_outcome = 'Complete') AS successful_dribbles,
    COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures,
    COUNT(*) FILTER (WHERE e.event_type = 'Interception') AS interceptions,
    COUNT(*) FILTER (WHERE e.event_type = 'Tackle') AS tackles
FROM events e
JOIN players p ON e.player_id = p.player_id
JOIN teams t ON e.team_id = t.team_id
GROUP BY e.match_id, e.player_id, p.player_name, e.team_id, t.team_name;

-- Team match summary
CREATE OR REPLACE VIEW v_team_match_summary AS
SELECT
    e.match_id,
    e.team_id,
    t.team_name,
    m.match_date,
    COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS passes_completed,
    COUNT(*) FILTER (WHERE e.event_type = 'Pass') AS passes_attempted,
    ROUND(
        COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL)::NUMERIC /
        NULLIF(COUNT(*) FILTER (WHERE e.event_type = 'Pass'), 0), 3
    ) AS pass_accuracy,
    COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots,
    SUM(e.xg) FILTER (WHERE e.event_type = 'Shot') AS total_xg,
    COUNT(*) FILTER (WHERE e.event_type = 'Shot' AND e.shot_outcome = 'Goal') AS goals,
    COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures,
    COUNT(*) FILTER (WHERE e.counterpress) AS counterpresses,
    COUNT(DISTINCT e.possession) AS possessions
FROM events e
JOIN teams t ON e.team_id = t.team_id
JOIN matches m ON e.match_id = m.match_id
GROUP BY e.match_id, e.team_id, t.team_name, m.match_date;

-- ============================================================================
-- MATERIALISED VIEWS: Pre-computed summaries for dashboard performance
-- Refreshed after each ingestion batch. Queries against these are instant.
-- ============================================================================

-- Materialised: Player season aggregates (used by dashboard player view)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_player_season_stats AS
SELECT
    e.player_id,
    p.player_name,
    e.team_id,
    t.team_name,
    m.season_id,
    COUNT(DISTINCT e.match_id) AS appearances,
    COUNT(*) FILTER (WHERE e.event_type = 'Shot' AND e.shot_outcome = 'Goal') AS goals,
    ROUND(COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0)::NUMERIC, 2) AS total_xg,
    COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots,
    ROUND(COALESCE(SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL), 0)::NUMERIC, 2) AS total_xa,
    COUNT(*) FILTER (WHERE e.key_pass) AS key_passes,
    COUNT(*) FILTER (WHERE e.assist) AS assists,
    COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS passes_completed,
    COUNT(*) FILTER (WHERE e.event_type = 'Pass') AS passes_attempted,
    COUNT(*) FILTER (WHERE e.event_type = 'Dribble' AND e.dribble_outcome = 'Complete') AS successful_dribbles,
    COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS pressures,
    COUNT(*) FILTER (WHERE e.event_type = 'Tackle') AS tackles,
    COUNT(*) FILTER (WHERE e.event_type = 'Interception') AS interceptions,
    -- Per-match rates
    ROUND(COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0)::NUMERIC /
        NULLIF(COUNT(DISTINCT e.match_id), 0), 3) AS xg_per_match,
    ROUND(COALESCE(SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL), 0)::NUMERIC /
        NULLIF(COUNT(DISTINCT e.match_id), 0), 3) AS xa_per_match,
    ROUND(COUNT(*) FILTER (WHERE e.event_type = 'Pressure')::NUMERIC /
        NULLIF(COUNT(DISTINCT e.match_id), 0), 1) AS pressures_per_match
FROM events e
JOIN players p ON e.player_id = p.player_id
JOIN teams t ON e.team_id = t.team_id
JOIN matches m ON e.match_id = m.match_id
WHERE e.player_id IS NOT NULL
GROUP BY e.player_id, p.player_name, e.team_id, t.team_name, m.season_id
HAVING COUNT(DISTINCT e.match_id) >= 2;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_player_season
    ON mv_player_season_stats (player_id, season_id);

-- Materialised: Team season summary (used by opponent profiling dashboard)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_team_season_stats AS
SELECT
    e.team_id,
    t.team_name,
    m.season_id,
    COUNT(DISTINCT e.match_id) AS matches_played,
    COUNT(*) FILTER (WHERE e.event_type = 'Pass' AND e.pass_outcome IS NULL) AS passes_completed,
    COUNT(*) FILTER (WHERE e.event_type = 'Pass') AS passes_attempted,
    COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS total_shots,
    ROUND(COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0)::NUMERIC, 2) AS total_xg,
    COUNT(*) FILTER (WHERE e.event_type = 'Shot' AND e.shot_outcome = 'Goal') AS total_goals,
    COUNT(*) FILTER (WHERE e.event_type = 'Pressure') AS total_pressures,
    COUNT(*) FILTER (WHERE e.counterpress) AS total_counterpresses,
    -- Per-match averages
    ROUND(COALESCE(SUM(e.xg) FILTER (WHERE e.event_type = 'Shot'), 0)::NUMERIC /
        NULLIF(COUNT(DISTINCT e.match_id), 0), 2) AS xg_per_match,
    ROUND(COUNT(*) FILTER (WHERE e.event_type = 'Shot')::NUMERIC /
        NULLIF(COUNT(DISTINCT e.match_id), 0), 1) AS shots_per_match,
    ROUND(COUNT(*) FILTER (WHERE e.event_type = 'Pressure')::NUMERIC /
        NULLIF(COUNT(DISTINCT e.match_id), 0), 1) AS pressures_per_match
FROM events e
JOIN teams t ON e.team_id = t.team_id
JOIN matches m ON e.match_id = m.match_id
GROUP BY e.team_id, t.team_name, m.season_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_team_season
    ON mv_team_season_stats (team_id, season_id);

-- Function to refresh all materialised views (call after ingestion)
CREATE OR REPLACE FUNCTION refresh_materialised_views()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_player_season_stats;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_team_season_stats;
END;
$$ LANGUAGE plpgsql;
