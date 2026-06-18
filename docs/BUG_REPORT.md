# Pipeline Bug Report & Resolution Log
**Project:** CoSQL NBA Spatial — IE7500 NLP Northeastern EDGE Summer 2026  
**Author:** Rosalina Torres  
**Date:** June 17, 2026  
**Purpose:** Engineering notes for final project paper — documents all bugs encountered during T1/T2 implementation and their resolutions.

---

## Bug 1 — Invalid nba_api Import Path
**File:** `collect_nba_data.py`  
**Severity:** Critical (script crashed on import)

### Symptom
```
ModuleNotFoundError: No module named 'nba_api.client.client'
```

### Root Cause
The original script imported a non-existent module:
```python
from nba_api.client.client import Client  # module does not exist
```
The nba_api library (v1.11.4) does not have a `client` submodule. The correct import path uses `nba_api.stats.endpoints`.

### Fix
Removed the invalid import. Added `import time` for rate limiting:
```python
from nba_api.stats.endpoints import shotchartdetail, playbyplayv3, commonteamroster, leaguegamefinder
import time
```

---

## Bug 2 — Wrong Season Format
**File:** `collect_nba_data.py`  
**Severity:** High (API returned 0 games)

### Symptom
```
Found 0 games for Celtics in 2023-24
```

### Root Cause
Season was passed as an integer `2023` but nba_api's `LeagueGameFinder` and `CommonTeamRoster` require a string in `"YYYY-YY"` format:
```python
SEASON = 2023  # WRONG — returns empty results
```

### Fix
```python
SEASON = '2023-24'  # CORRECT — string format required by nba_api
```

---

## Bug 3 — Wrong Column Names (CommonTeamRoster)
**File:** `collect_nba_data.py`  
**Severity:** High (KeyError crash)

### Symptom
```
KeyError: "['PLAYER_NAME', 'DRAFT_YEAR'] not in index"
```

### Root Cause
The NBA_API_REFERENCE.md documented assumed column names (`PLAYER_NAME`, `DRAFT_YEAR`) that do not exist in the actual `CommonTeamRoster` response. Actual columns are:
```
['TeamID', 'SEASON', 'LeagueID', 'PLAYER', 'NICKNAME', 'PLAYER_SLUG',
 'NUM', 'POSITION', 'HEIGHT', 'WEIGHT', 'BIRTH_DATE', 'AGE', 'EXP',
 'SCHOOL', 'PLAYER_ID', 'HOW_ACQUIRED']
```
Note: column is `PLAYER` not `PLAYER_NAME`, and `DRAFT_YEAR` does not exist.

### Fix
```python
players = roster[['PLAYER_ID', 'PLAYER', 'POSITION', 'HEIGHT', 'WEIGHT']].copy()
players = players.rename(columns={'PLAYER': 'PLAYER_NAME'})
players['DRAFT_YEAR'] = None  # not available in this endpoint
```

---

## Bug 4 — Invalid ShotChartDetail Parameter
**File:** `collect_nba_data.py`  
**Severity:** High (all shot chart fetches failed silently)

### Symptom
```
ShotChartDetail.__init__() got an unexpected keyword argument 'game_id_flag'
Found 0 shot attempts across all games
```

### Root Cause
The reference documentation used `game_id_flag='Y'` which was removed in nba_api v1.x. The correct parameter is `game_id_nullable`:
```python
# WRONG:
shotchartdetail.ShotChartDetail(game_id_flag='Y', game_id=game_id)

# CORRECT:
shotchartdetail.ShotChartDetail(game_id_nullable=game_id, season_nullable=SEASON)
```

### Fix
Updated all `ShotChartDetail` calls to use `game_id_nullable` and added `context_measure_simple='FGA'` for field goal attempts.

---

## Bug 5 — DataFrame Iteration (TypeError)
**File:** `collect_nba_data.py`  
**Severity:** High (crash in shot chart and play-by-play loops)

### Symptom
```
TypeError: string indices must be integers, not 'str'
```

### Root Cause
`fetch_games()` returns a pandas DataFrame, but the loops in `fetch_shot_charts()` and `fetch_play_by_play()` iterated over it as if it were a list of dicts:
```python
for i, game in enumerate(games):      # WRONG — iterates over column names
    game_id = game['GAME_ID']
```

### Fix
```python
for i, (_, game) in enumerate(games.iterrows()):  # CORRECT
    game_id = game['GAME_ID']
```

---

## Bug 6 — Foreign Key Violation (Players Table)
**File:** `collect_nba_data.py` / `schema.sql`  
**Severity:** High (load_into_db failed)

### Symptom
```
psycopg2.errors.ForeignKeyViolation: insert or update on table "shot_charts"
violates foreign key constraint "shot_charts_player_id_fkey"
Key (player_id)=(1630205) is not present in table "players"
```

### Root Cause
`fetch_players()` originally loaded only the Celtics roster (17 players) using `CommonTeamRoster`. However, shot charts include all players who appeared in Celtics games — including opposing team players — resulting in FK violations when inserting shots by non-Celtics players.

### Fix
Replaced `CommonTeamRoster` with `nba_api.stats.static.players.get_players()` which returns all 5,103 NBA players:
```python
from nba_api.stats.static import players as nba_players
all_players = nba_players.get_players()
players_df = pd.DataFrame(all_players)
```
This eliminates FK violations while keeping the relational integrity intact.

---

## Bug 7 — PlayByPlayV3 Column Name Mismatch
**File:** `collect_nba_data.py`  
**Severity:** High (KeyError in load_into_db)

### Symptom
```
KeyError: 'GAME_ID'
```

### Root Cause
`PlayByPlayV3` returns camelCase column names, not the UPPERCASE convention used by other nba_api endpoints:
```
# Actual columns: gameId, actionNumber, actionType, clock, personId, scoreHome, scoreAway
# Expected (assumed): GAME_ID, EVENTNUM, ACTION_TYPE, PCTIMESTRING, PLAYER_ID, SCORE
```

### Fix
Updated `load_into_db` to use correct camelCase column names:
```python
play_rows = [
    (row.get('actionNumber'), str(row.get('gameId', '')).zfill(10),
     row.get('actionType'), row.get('clock'),
     str(row.get('personId', '')), None,
     str(row.get('scoreHome', '')) + '-' + str(row.get('scoreAway', '')))
    for _, row in plays.iterrows()
]
```

---

## Bug 8 — Spatial Zone Unit Mismatch (Critical Annotation Bug)
**Files:** `schema.sql`, `query_classes_and_clarify_templates.md`, `woz_annotation_template.csv`  
**Severity:** Critical (all zone-based queries returned 0 results)

### Symptom
```sql
-- Above the break 3s:
SELECT COUNT(*) FROM shot_charts WHERE y > 90 AND distance > 220;
-- Result: 0 rows
```

### Root Cause
nba_api uses **two different units** for spatial data:
- `LOC_X`, `LOC_Y` (stored as `x`, `y`) — **tenths of feet** (range: x=-250 to 250, y=-52 to 887)
- `SHOT_DISTANCE` (stored as `distance`) — **whole feet** (range: 0 to ~76)

The original zone definitions incorrectly applied the tenths-of-feet scale to `distance`:
```sql
distance > 220  -- WRONG: 220 feet is impossible; max is ~76
distance > 22   -- CORRECT: 22 feet ≈ NBA 3-point line above the break
```

### Impact
- `above_break_3`: returned 0 (should be ~2,706)
- `restricted_area`: severely under-counted
- `mid_range`: returned 0

### Fix
Updated all distance-based zone boundaries to whole-feet units:

| Zone | Before (broken) | After (correct) |
|---|---|---|
| above_break_3 | `distance > 220` | `distance > 22` |
| restricted_area | `distance <= 40` | `distance <= 4` |
| mid_range | `distance BETWEEN 80 AND 220` | `distance BETWEEN 8 AND 22` |

### Verified Row Counts (post-fix)
| Zone | Count |
|---|---|
| Left corner 3 | 382 |
| Right corner 3 | 394 |
| Above break 3 | 2,706 |
| In the paint | 3,344 |
| Mid-range | 1,383 |

### Annotation Impact
Any WOZ pairs written before this fix using distance-based zone filters would have produced empty result sets. The 10 seed annotation pairs were reviewed — only row 2 (left corner 3) and row 3 (above break, using y > 90 only) were affected. Row 2 is correct (uses x/y only). Row 3 was not affected as it did not include a distance filter.

---

## Bug 9 — SQL Integer Subtraction in Season Filter
**File:** `woz_annotation_template.csv` row 5  
**Severity:** Medium (silent wrong result)

### Symptom
Query returned results for season `1999` instead of `2023-24`.

### Root Cause
```sql
WHERE season = 2023-24  -- SQL evaluates as: season = 1999 (integer subtraction)
```

### Fix
```sql
WHERE season_type = '2023-24'  -- quoted string literal
```

---

## Bug 10 — shot_clock Column Semantic Mismatch
**Files:** `query_classes_and_clarify_templates.md`, `woz_annotation_template.csv` row 9  
**Severity:** Medium (misleading annotation, wrong query semantics)

### Symptom
Annotation pairs referencing "shot clock time" executed queries against `SECONDS_REMAINING` which is actually period time remaining, not shot-clock time.

### Root Cause
nba_api's `ShotChartDetail` returns `SECONDS_REMAINING` which represents **time left in the period** (e.g., 45 seconds left in Q3), not time remaining on the shot clock (which would be 0–24 seconds). The column was mislabeled in documentation as `shot_clock`.

### Fix
- Renamed column to `period_seconds_remaining` in `schema.sql` and `load_into_db`
- Updated Class 8 in `query_classes_and_clarify_templates.md` to note shot-clock data is unavailable
- Row 9 in `woz_annotation_template.csv` flagged as `clarification_needed`

---

## Bug 11 — MINUTES_REMAINING Not Stored (Clock Precision Lost)
**Files:** `collect_nba_data.py`, `schema.sql`  
**Severity:** High (sub-minute temporal queries return 0 or NULL)

### Symptom
```sql
SELECT COUNT(*) FROM shot_charts WHERE period = 4 AND (minutes_remaining * 60 + period_seconds_remaining) <= 120;
-- Result: 0 (minutes_remaining is NULL for all rows)
```

### Root Cause
`ShotChartDetail` returns both `MINUTES_REMAINING` and `SECONDS_REMAINING` as separate columns representing the MM:SS clock display. Only `SECONDS_REMAINING` (renamed `period_seconds_remaining`) was stored in the schema. Without `MINUTES_REMAINING`, the seconds component alone (0–59) is insufficient to determine total time remaining in a period.

### Fix
Added `minutes_remaining INTEGER` column to `schema.sql` and `shot_charts` table (via `ALTER TABLE`). Updated `collect_nba_data.py` insert to include both:
```python
row.get('MINUTES_REMAINING'),
row.get('SECONDS_REMAINING'),
```
Total seconds formula for annotation SQL: `minutes_remaining * 60 + period_seconds_remaining`

### Status
Schema fixed. Existing T2 data has NULL `minutes_remaining` — requires a re-collection run to backfill. Annotation pairs 3, 4, 11, 12, 17 marked `needs_revision` until backfilled.

---

## Bug 12 — Playoff Shot Charts Not Loaded (Silent Data Gap)
**Files:** `collect_nba_data.py`  
**Severity:** High (playoff temporal queries return 0)

### Symptom
```sql
SELECT COUNT(*) FROM shot_charts WHERE game_id IN (SELECT game_id FROM games WHERE season_type = 'Playoff');
-- Result: 0 (despite 24 playoff games in games table)
```

### Root Cause
`ShotChartDetail` returns 0 results when `game_id_nullable` is set to a playoff game ID (`004xxxxxxx`). This is an undocumented API constraint — the endpoint silently returns empty results for playoff game IDs when using the `game_id_nullable` filter. The regular-season game-by-game loop in `fetch_shot_charts()` masked this because regular season IDs (`002xxxxxxx`) work fine.

**Key finding (diagnosed via direct API test):**
```python
# This returns 0 shots — game_id_nullable blocks playoff results
ShotChartDetail(team_id=1610612738, game_id_nullable='0042300101', ...).get_data_frames()[0]

# This returns 1593 shots — correct approach for playoffs
ShotChartDetail(team_id=1610612738, season_type_all_star='Playoffs', ...).get_data_frames()[0]
```

### Fix
Fetched all Celtics 2023-24 playoff shots in one call using `season_type_all_star='Playoffs'` (no `game_id_nullable`). Inserted 1,593 playoff shot rows directly into `shot_charts`.

`collect_nba_data.py` should be updated to add a separate playoff collection pass using `season_type_all_star='Playoffs'` instead of iterating through playoff game IDs individually.

### Status
**RESOLVED.** 1,593 playoff shots loaded (game IDs `0042300101`–`0042300405`). Total shot_charts: 8,989 rows. Annotation pairs 7, 8 (Class 2 Temporal), 7 (Class 7 Game Context) upgraded to `approved`.

---

## Bug 13 — home_team / away_team NULL (Wrong LeagueGameFinder Column Names)
**Files:** `collect_nba_data.py`  
**Severity:** High (home/away game queries return 0)

### Symptom
```sql
SELECT COUNT(*) FROM games WHERE home_team ILIKE '%Boston%';
-- Result: 0 (home_team is NULL for all 106 rows)
```

### Root Cause
`load_into_db` used `row.get('HOME_TEAM_NAME')` and `row.get('AWAY_TEAM_NAME')` but `LeagueGameFinder` does not return those columns. The actual columns are:
- `TEAM_NAME` — the tracked team (Boston Celtics)
- `MATCHUP` — `"BOS vs. LAL"` (home game) or `"BOS @ LAL"` (away game)

### Fix
Added `parse_teams()` helper in `load_into_db` to derive home/away from `MATCHUP`:
```python
if 'vs.' in matchup:
    return team, opponent   # home, away
elif '@' in matchup:
    return opponent, team   # home, away
```

### Status
Script patched. Existing 106 game rows have NULL `home_team`/`away_team` — requires re-collection run. Class 4 annotation pairs 12, 13, 14 marked `needs_revision`.

---

## Summary Table

| # | Bug | Severity | File | Status |
|---|---|---|---|---|
| 1 | Invalid nba_api import path | Critical | collect_nba_data.py | ✅ Fixed |
| 2 | Wrong season format (int vs string) | High | collect_nba_data.py | ✅ Fixed |
| 3 | Wrong CommonTeamRoster column names | High | collect_nba_data.py | ✅ Fixed |
| 4 | Invalid ShotChartDetail parameter | High | collect_nba_data.py | ✅ Fixed |
| 5 | DataFrame iteration (enumerate vs iterrows) | High | collect_nba_data.py | ✅ Fixed |
| 6 | FK violation — Celtics-only player table | High | collect_nba_data.py | ✅ Fixed |
| 7 | PlayByPlayV3 camelCase column mismatch | High | collect_nba_data.py | ✅ Fixed |
| 8 | Spatial zone unit mismatch (tenths vs feet) | Critical | schema.sql, docs, CSV | ✅ Fixed |
| 9 | SQL integer subtraction in season filter | Medium | woz_annotation_template.csv | ✅ Fixed |
| 10 | shot_clock semantic mismatch | Medium | docs, CSV | ✅ Fixed |
| 11 | MINUTES_REMAINING not stored (clock precision) | High | collect_nba_data.py, schema.sql | ✅ Fixed (needs re-collection) |
| 12 | Playoff shot charts not loaded (silent data gap) | High | collect_nba_data.py | ✅ Resolved — use season_type_all_star='Playoffs', not game_id_nullable |
| 13 | home_team / away_team NULL (wrong LeagueGameFinder columns) | High | collect_nba_data.py | ✅ Fixed (needs re-collection) |

---

## Lessons for Final Paper

1. **API documentation lag** — nba_api parameter names changed between versions; always inspect `inspect.signature()` or source before assuming parameter names from tutorials.
2. **Unit consistency** — spatial APIs frequently mix coordinate systems. Always verify units empirically against real data before building zone filters.
3. **Static vs. dynamic player lists** — roster endpoints (per-team) are insufficient for relational integrity when data spans multiple teams; use the full league static list.
4. **camelCase vs UPPERCASE** — nba_api is inconsistent: most endpoints return UPPERCASE columns, but `PlayByPlayV3` returns camelCase. Always print `.columns.tolist()` before writing insert logic.
5. **Silent failures** — several bugs (wrong season format, wrong parameter name, missing columns) caused API calls to return empty DataFrames or NULL values with no error. Always verify counts at the end of every collection step.
6. **Partial columns from multi-field clocks** — API endpoints sometimes split a logical value (MM:SS clock) into two columns. Storing only one component silently loses precision. Always check what related columns exist when storing time data.
