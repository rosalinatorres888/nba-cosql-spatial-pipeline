-- Bug 8 live verification — spatial zone unit mismatch (tenths-of-feet vs whole feet)
-- Run:  psql nba_spatial < scripts/verify_bug8.sql
--
-- Section 1: the pre-fix filters must return ~0 rows (distance is whole feet, max ~76,
-- so distance > 220 is impossible). If these return large counts, units have changed.
SELECT 'SYMPTOM: broken above_break_3 (distance > 220) — expect 0' AS check, COUNT(*) AS rows
FROM shot_charts WHERE y > 90 AND distance > 220
UNION ALL
SELECT 'SYMPTOM: broken mid_range (distance 80-220) — expect ~0', COUNT(*)
FROM shot_charts WHERE distance BETWEEN 80 AND 220;

-- Section 2: corrected zone filters, regular-season scope (matches the counts
-- documented in docs/BUG_REPORT.md Bug 8). NOTE: season_type value is 'Regular',
-- not 'Regular Season'.
SELECT 'left_corner_3 — expect 382' AS zone, COUNT(*) AS rows
FROM shot_charts s JOIN games g ON g.game_id = s.game_id AND g.season_type = 'Regular'
WHERE x <= -220 AND y <= 90
UNION ALL
SELECT 'right_corner_3 — expect 394', COUNT(*)
FROM shot_charts s JOIN games g ON g.game_id = s.game_id AND g.season_type = 'Regular'
WHERE x >= 220 AND y <= 90
UNION ALL
SELECT 'above_break_3 — expect ~2710', COUNT(*)
FROM shot_charts s JOIN games g ON g.game_id = s.game_id AND g.season_type = 'Regular'
WHERE y > 90 AND distance > 22
UNION ALL
SELECT 'in_the_paint — expect 3344', COUNT(*)
FROM shot_charts s JOIN games g ON g.game_id = s.game_id AND g.season_type = 'Regular'
WHERE ABS(x) <= 80 AND y <= 190
UNION ALL
SELECT 'mid_range — expect 1383', COUNT(*)
FROM shot_charts s JOIN games g ON g.game_id = s.game_id AND g.season_type = 'Regular'
WHERE distance BETWEEN 8 AND 22;

-- Section 3: full-table zone counts (regular season + playoffs), for reference.
SELECT 'ALL GAMES left_corner_3' AS zone, COUNT(*) AS rows FROM shot_charts WHERE x <= -220 AND y <= 90
UNION ALL SELECT 'ALL GAMES right_corner_3', COUNT(*) FROM shot_charts WHERE x >= 220 AND y <= 90
UNION ALL SELECT 'ALL GAMES above_break_3', COUNT(*) FROM shot_charts WHERE y > 90 AND distance > 22
UNION ALL SELECT 'ALL GAMES in_the_paint', COUNT(*) FROM shot_charts WHERE ABS(x) <= 80 AND y <= 190
UNION ALL SELECT 'ALL GAMES mid_range', COUNT(*) FROM shot_charts WHERE distance BETWEEN 8 AND 22;
