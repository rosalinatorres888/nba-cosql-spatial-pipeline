-- CoSQL NBA Spatial — PostgreSQL Schema
-- Project: IE7500 Natural Language Processing | Northeastern EDGE | Summer 2026
-- Author:  Rosalina Torres
-- Purpose: Backing database for conversational text-to-SQL over NBA spatial data

-- ============================================================
-- PLAYERS
-- ============================================================
CREATE TABLE IF NOT EXISTS players (
    player_id   INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    team        TEXT,                   -- e.g. 'BOS'
    position    TEXT,                   -- e.g. 'SF', 'PG'
    height      TEXT,                   -- e.g. '6-8' (nba_api returns as string)
    weight      TEXT,                   -- e.g. '210'
    draft_year  INTEGER
);

-- ============================================================
-- GAMES
-- ============================================================
CREATE TABLE IF NOT EXISTS games (
    game_id     TEXT    PRIMARY KEY,    -- 10-digit zero-padded e.g. '0022300010'
    date        DATE,
    home_team   TEXT,                   -- e.g. 'Boston Celtics'
    away_team   TEXT,
    venue       TEXT,                   -- 'TBD' — not in nba_api
    score       INTEGER,                -- points scored by tracked team
    season_type TEXT                    -- 'Regular' or 'Playoff' (derived from GAME_ID prefix: 002=Regular, 004=Playoff)
);

-- ============================================================
-- SHOT CHARTS
-- NOTE: MINUTES_REMAINING and SECONDS_REMAINING from nba_api are the
--       MM:SS clock display components — NOT total seconds, NOT shot clock.
--       Total seconds left in period = minutes_remaining * 60 + period_seconds_remaining
--       No shot-clock column exists in nba_api shot chart data.
-- season_type values: 'Regular' and 'Playoff' (not 'Regular Season' / 'Playoffs')
-- ============================================================
CREATE TABLE IF NOT EXISTS shot_charts (
    id                        SERIAL PRIMARY KEY,
    event_id                  INTEGER, -- nba_api GAME_EVENT_ID: natural key within a game
    player_id                 INTEGER REFERENCES players(player_id),
    game_id                   TEXT    REFERENCES games(game_id),
    shot_type                 TEXT,    -- '2PT Field Goal' or '3PT Field Goal'
    x                         INTEGER, -- court coordinate (-250 to +250)
    y                         INTEGER, -- court coordinate (0 to 470)
    distance                  INTEGER, -- shot distance in feet
    made_flag                 SMALLINT CHECK (made_flag IN (0, 1)),
    defender                  TEXT,    -- NULL — not available in shot chart API
    minutes_remaining         INTEGER, -- minutes component of period clock (0-11)
    period_seconds_remaining  INTEGER, -- seconds component of period clock (0-59) — NOT total seconds
    period                    INTEGER  -- 1-4 regulation, 5+ overtime
);

-- Natural key: one row per game event. Makes collection idempotent via
-- ON CONFLICT DO NOTHING (re-running collect/load scripts cannot duplicate rows).
CREATE UNIQUE INDEX IF NOT EXISTS uq_shot_charts_game_event
    ON shot_charts(game_id, event_id);

CREATE INDEX IF NOT EXISTS idx_shot_charts_player ON shot_charts(player_id);
CREATE INDEX IF NOT EXISTS idx_shot_charts_game   ON shot_charts(game_id);
CREATE INDEX IF NOT EXISTS idx_shot_charts_zone   ON shot_charts(x, y);

-- ============================================================
-- PLAY BY PLAY
-- ============================================================
CREATE TABLE IF NOT EXISTS play_by_play (
    id            SERIAL PRIMARY KEY,
    event_id      INTEGER,
    game_id       TEXT    REFERENCES games(game_id),
    event_type    TEXT,                -- e.g. 'Made Shot', 'Foul', 'Turnover'
    game_clock    TEXT,                -- 'MM:SS' format e.g. '11:45'
    player_ids    TEXT,                -- player_id as string (JSON array if multi)
    lineups       TEXT,                -- NULL — not directly available in API
    running_score TEXT                 -- e.g. '102 - 98'
);

-- Natural key: one row per game event (event_id = actionNumber from PlayByPlayV3).
CREATE UNIQUE INDEX IF NOT EXISTS uq_pbp_game_event
    ON play_by_play(game_id, event_id);

CREATE INDEX IF NOT EXISTS idx_pbp_game      ON play_by_play(game_id);
CREATE INDEX IF NOT EXISTS idx_pbp_event     ON play_by_play(event_type);

-- ============================================================
-- SPATIAL ZONE REFERENCE (lookup table for annotation)
-- IMPORTANT UNIT NOTE (verified against live nba_api data Jun 2026):
--   x, y (LOC_X, LOC_Y) = tenths of feet  e.g. x=-220 means 22 feet left of center
--   distance (SHOT_DISTANCE) = whole feet  e.g. distance=22 means 22 feet from basket
--   Do NOT use distance > 220 — correct filter is distance > 22
-- ============================================================
CREATE TABLE IF NOT EXISTS spatial_zones (
    zone_name   TEXT PRIMARY KEY,
    description TEXT,
    sql_filter  TEXT    -- canonical WHERE clause fragment for this zone
);

INSERT INTO spatial_zones (zone_name, description, sql_filter) VALUES
    ('left_corner_3',   'Left corner 3-pointer',          'x <= -220 AND y <= 90'),
    ('right_corner_3',  'Right corner 3-pointer',         'x >= 220 AND y <= 90'),
    ('above_break_3',   'Above the break 3-pointer',      'y > 90 AND distance > 22'),
    ('restricted_area', 'Restricted area near basket',    'distance <= 4 OR (ABS(x) <= 80 AND y <= 190)'),
    ('in_the_paint',    'In the paint (full lane)',        'ABS(x) <= 80 AND y <= 190'),
    ('mid_range',       'Mid-range (non-3PT)',             'distance BETWEEN 8 AND 22')
ON CONFLICT (zone_name) DO NOTHING;
