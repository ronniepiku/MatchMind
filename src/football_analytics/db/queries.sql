-- ============================================================================
-- Example Optimised Queries for Football Analysis
-- Each query includes EXPLAIN notes and football context
-- ============================================================================

-- ============================================================================
-- 1. OPPONENT PROFILE: Summarise an opponent's attacking patterns
--    Use case: Pre-match preparation — understand how opponent builds attacks
-- ============================================================================
-- EXPLAIN: Uses idx_events_team + idx_events_match_type
-- Expected: Index Scan on idx_events_team → Filter → Aggregate
-- Cost: O(events_for_team) — fast for single-team lookups

SELECT
    t.team_name,
    e.play_pattern,
    COUNT(*) AS possessions,
    COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots_from_pattern,
    ROUND(AVG(e.xg) FILTER (WHERE e.event_type = 'Shot'), 3) AS avg_xg_per_shot,
    COUNT(*) FILTER (WHERE e.event_type = 'Shot' AND e.shot_outcome = 'Goal') AS goals
FROM events e
JOIN teams t ON e.team_id = t.team_id
WHERE e.team_id = :opponent_team_id
  AND e.match_id IN (
      SELECT match_id FROM matches
      WHERE (home_team_id = :opponent_team_id OR away_team_id = :opponent_team_id)
        AND season_id = :season_id
  )
  AND e.event_type IN ('Shot', 'Pass', 'Carry')
GROUP BY t.team_name, e.play_pattern
ORDER BY shots_from_pattern DESC;

-- ============================================================================
-- 2. PLAYER PERFORMANCE: Rolling xG + xA over last N matches
--    Use case: Track form / identify trending performers
-- ============================================================================
-- EXPLAIN: Uses idx_events_player + join on matches for ordering
-- Window function over match_date provides rolling aggregation

WITH player_match_xg AS (
    SELECT
        e.player_id,
        p.player_name,
        e.match_id,
        m.match_date,
        SUM(e.xg) FILTER (WHERE e.event_type = 'Shot') AS match_xg,
        SUM(e.xa) FILTER (WHERE e.xa IS NOT NULL) AS match_xa,
        COUNT(*) FILTER (WHERE e.event_type = 'Shot') AS shots
    FROM events e
    JOIN players p ON e.player_id = p.player_id
    JOIN matches m ON e.match_id = m.match_id
    WHERE e.player_id = :player_id
    GROUP BY e.player_id, p.player_name, e.match_id, m.match_date
)
SELECT
    player_name,
    match_date,
    match_xg,
    match_xa,
    shots,
    AVG(match_xg) OVER (ORDER BY match_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS rolling_5_xg,
    AVG(match_xa) OVER (ORDER BY match_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS rolling_5_xa
FROM player_match_xg
ORDER BY match_date DESC
LIMIT 20;

-- ============================================================================
-- 3. PRESSING INTENSITY: Team pressing actions by zone (1/3 splits)
--    Use case: Identify high-press vs mid-block tendencies
-- ============================================================================
-- EXPLAIN: Uses idx_events_team + location filter
-- Pitch zones: Defensive (0-40), Middle (40-80), Attacking (80-120)

SELECT
    t.team_name,
    CASE
        WHEN e.location_x < 40 THEN 'Defensive Third'
        WHEN e.location_x < 80 THEN 'Middle Third'
        ELSE 'Attacking Third'
    END AS pitch_zone,
    COUNT(*) AS press_actions,
    ROUND(COUNT(*)::NUMERIC / NULLIF(
        (SELECT COUNT(DISTINCT minute) FROM events WHERE match_id = e.match_id), 0
    ), 2) AS presses_per_minute,
    COUNT(*) FILTER (WHERE e.counterpress) AS counterpresses
FROM events e
JOIN teams t ON e.team_id = t.team_id
WHERE e.event_type = 'Pressure'
  AND e.team_id = :team_id
  AND e.match_id = :match_id
GROUP BY t.team_name, pitch_zone
ORDER BY
    CASE pitch_zone
        WHEN 'Attacking Third' THEN 1
        WHEN 'Middle Third' THEN 2
        ELSE 3
    END;

-- ============================================================================
-- 4. PASSING NETWORK: Average positions and pass connections between starters
--    Use case: Understand team shape and key passing relationships
-- ============================================================================
-- EXPLAIN: Uses idx_events_match_type + join on lineups
-- Only first half to avoid substitution noise

WITH starter_passes AS (
    SELECT
        e.player_id AS passer_id,
        e.pass_recipient_id AS receiver_id,
        e.location_x,
        e.location_y,
        e.end_location_x,
        e.end_location_y
    FROM events e
    JOIN lineups l ON e.match_id = l.match_id
                  AND e.team_id = l.team_id
                  AND e.player_id = l.player_id
    WHERE e.match_id = :match_id
      AND e.team_id = :team_id
      AND e.event_type = 'Pass'
      AND e.pass_outcome IS NULL  -- completed passes only
      AND e.period = 1            -- first half only
      AND l.is_starter = TRUE
),
avg_positions AS (
    SELECT
        passer_id AS player_id,
        AVG(location_x) AS avg_x,
        AVG(location_y) AS avg_y,
        COUNT(*) AS passes_made
    FROM starter_passes
    GROUP BY passer_id
)
SELECT
    sp.passer_id,
    p1.player_name AS passer,
    sp.receiver_id,
    p2.player_name AS receiver,
    COUNT(*) AS pass_count,
    ap.avg_x AS passer_avg_x,
    ap.avg_y AS passer_avg_y
FROM starter_passes sp
JOIN players p1 ON sp.passer_id = p1.player_id
JOIN players p2 ON sp.receiver_id = p2.player_id
JOIN avg_positions ap ON sp.passer_id = ap.player_id
GROUP BY sp.passer_id, p1.player_name, sp.receiver_id, p2.player_name, ap.avg_x, ap.avg_y
HAVING COUNT(*) >= 3  -- filter noise
ORDER BY pass_count DESC;

-- ============================================================================
-- 5. xG TIMELINE: Cumulative xG by minute for match momentum visualisation
--    Use case: Post-match report showing which team created better chances
-- ============================================================================
-- EXPLAIN: Uses idx_events_match_minute for fast time-ordered scans

SELECT
    e.minute,
    e.team_id,
    t.team_name,
    e.xg,
    e.shot_outcome,
    SUM(e.xg) OVER (PARTITION BY e.team_id ORDER BY e.minute, e.second) AS cumulative_xg
FROM events e
JOIN teams t ON e.team_id = t.team_id
WHERE e.match_id = :match_id
  AND e.event_type = 'Shot'
ORDER BY e.minute, e.second;
