-- Migration 001: idempotent data collection
-- For databases created before schema.sql added event_id + unique natural keys.
-- Run once:  psql nba_spatial < migrations/001_idempotent_collection.sql
--
-- Step 1: add the event_id column to shot_charts.
ALTER TABLE shot_charts ADD COLUMN IF NOT EXISTS event_id INTEGER;

-- Step 2: remove duplicate rows created by earlier non-idempotent re-runs.
-- Existing rows have event_id = NULL, so dedupe on the full value tuple,
-- keeping the lowest id of each duplicate group.
DELETE FROM shot_charts a
USING shot_charts b
WHERE a.id > b.id
  AND a.game_id IS NOT DISTINCT FROM b.game_id
  AND a.player_id IS NOT DISTINCT FROM b.player_id
  AND a.shot_type IS NOT DISTINCT FROM b.shot_type
  AND a.x IS NOT DISTINCT FROM b.x
  AND a.y IS NOT DISTINCT FROM b.y
  AND a.distance IS NOT DISTINCT FROM b.distance
  AND a.made_flag IS NOT DISTINCT FROM b.made_flag
  AND a.minutes_remaining IS NOT DISTINCT FROM b.minutes_remaining
  AND a.period_seconds_remaining IS NOT DISTINCT FROM b.period_seconds_remaining
  AND a.period IS NOT DISTINCT FROM b.period;

DELETE FROM play_by_play a
USING play_by_play b
WHERE a.id > b.id
  AND a.game_id IS NOT DISTINCT FROM b.game_id
  AND a.event_id IS NOT DISTINCT FROM b.event_id
  AND a.event_type IS NOT DISTINCT FROM b.event_type
  AND a.game_clock IS NOT DISTINCT FROM b.game_clock
  AND a.player_ids IS NOT DISTINCT FROM b.player_ids
  AND a.running_score IS NOT DISTINCT FROM b.running_score;

-- Step 3: enforce the natural keys used by ON CONFLICT DO NOTHING.
-- Note: rows with NULL event_id (pre-migration data) are not deduped by these
-- indexes; a fresh re-collection will populate event_id going forward.
CREATE UNIQUE INDEX IF NOT EXISTS uq_shot_charts_game_event
    ON shot_charts(game_id, event_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pbp_game_event
    ON play_by_play(game_id, event_id);
