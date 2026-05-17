-- ============================================================================
-- Event Table Partitioning by season_id
-- ============================================================================
-- Partitioning enables partition pruning: queries filtering by season_id
-- only scan the relevant partition, dramatically improving performance at scale.
--
-- Migration strategy: Create partitioned table → copy data → swap names.
-- ============================================================================

-- Step 1: Create the partitioned table structure
CREATE TABLE IF NOT EXISTS events_partitioned (
    event_id         UUID NOT NULL,
    match_id         INTEGER NOT NULL,
    season_id        INTEGER NOT NULL,  -- partition key (denormalised from matches)
    team_id          INTEGER NOT NULL,
    player_id        INTEGER,
    event_type       VARCHAR(50) NOT NULL,
    period           SMALLINT NOT NULL,
    timestamp        TIME NOT NULL,
    minute           SMALLINT NOT NULL,
    second           SMALLINT,
    possession       INTEGER,
    possession_team_id INTEGER,
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
    pass_recipient_id INTEGER,
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
    raw_json         JSONB,
    PRIMARY KEY (event_id, season_id)
) PARTITION BY RANGE (season_id);

-- Step 2: Create partitions for known seasons
-- StatsBomb open data season IDs
CREATE TABLE IF NOT EXISTS events_season_2020 PARTITION OF events_partitioned
    FOR VALUES FROM (1) TO (30);

CREATE TABLE IF NOT EXISTS events_season_2021 PARTITION OF events_partitioned
    FOR VALUES FROM (30) TO (50);

CREATE TABLE IF NOT EXISTS events_season_2022 PARTITION OF events_partitioned
    FOR VALUES FROM (50) TO (80);

CREATE TABLE IF NOT EXISTS events_season_2023 PARTITION OF events_partitioned
    FOR VALUES FROM (80) TO (110);

CREATE TABLE IF NOT EXISTS events_season_2024 PARTITION OF events_partitioned
    FOR VALUES FROM (110) TO (140);

CREATE TABLE IF NOT EXISTS events_season_default PARTITION OF events_partitioned
    DEFAULT;

-- Step 3: Create indexes on the partitioned table (automatically propagated to partitions)
CREATE INDEX IF NOT EXISTS idx_ep_match_type
    ON events_partitioned (match_id, event_type);

CREATE INDEX IF NOT EXISTS idx_ep_player
    ON events_partitioned (player_id, event_type);

CREATE INDEX IF NOT EXISTS idx_ep_team
    ON events_partitioned (team_id, event_type);

CREATE INDEX IF NOT EXISTS idx_ep_match_minute
    ON events_partitioned (match_id, minute);

CREATE INDEX IF NOT EXISTS idx_ep_location
    ON events_partitioned (event_type, location_x, location_y)
    WHERE location_x IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ep_xg
    ON events_partitioned (xg)
    WHERE xg IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ep_possession
    ON events_partitioned (match_id, possession);

-- Step 4: Migration function — copies data from old events table to partitioned table
CREATE OR REPLACE FUNCTION migrate_to_partitioned_events()
RETURNS VOID AS $$
BEGIN
    -- Insert from old table with season_id join
    INSERT INTO events_partitioned
    SELECT e.*, m.season_id
    FROM events e
    JOIN matches m ON e.match_id = m.match_id
    ON CONFLICT DO NOTHING;

    -- Rename tables (atomic swap)
    ALTER TABLE events RENAME TO events_legacy;
    ALTER TABLE events_partitioned RENAME TO events;

    RAISE NOTICE 'Migration complete. Old table preserved as events_legacy.';
END;
$$ LANGUAGE plpgsql;

-- Step 5: Function to create a new partition dynamically
CREATE OR REPLACE FUNCTION create_season_partition(
    p_season_id_start INTEGER,
    p_season_id_end INTEGER,
    p_partition_name TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_name TEXT;
BEGIN
    v_name := COALESCE(p_partition_name,
        'events_season_' || p_season_id_start || '_' || p_season_id_end);

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF events_partitioned
         FOR VALUES FROM (%s) TO (%s)',
        v_name, p_season_id_start, p_season_id_end
    );

    RAISE NOTICE 'Created partition: %', v_name;
END;
$$ LANGUAGE plpgsql;
