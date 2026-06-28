# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Conversational Text-to-SQL (CoSQL) pipeline over Boston Celtics 2023–24 NBA shot-chart data. Users ask multi-turn basketball questions in natural language; the system resolves coreferences across turns and maps each utterance to an executable PostgreSQL query. Method: DIN-SQL-style few-shot prompting (no fine-tuning) using Claude Opus 4.8 with adaptive thinking.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Database setup (run once)
createdb nba_spatial
psql nba_spatial < schema.sql
cp .env.example .env  # then add ANTHROPIC_API_KEY and DB credentials

# Collect NBA data from nba_api into PostgreSQL
python collect_nba_data.py

# Load pre-exported CSVs into PostgreSQL (alternative to collect_nba_data.py)
python load_csvs_to_db.py --season 2023-24 --season-type "Regular Season"
python load_csvs_to_db.py --season 2023-24 --season-type Playoffs

# Run evaluation on held-out test split (requires live DB + ANTHROPIC_API_KEY)
python model/evaluate.py --split 0.2 --seed 42

# Run inter-annotator agreement report
python kappa_report.py

# Run inference directly (module __main__)
python model/nl2sql.py
```

## Architecture

```
nba_api → PostgreSQL (nba_spatial) → annotation/  → model/nl2sql.py
           4 tables, ~60K rows        139 NL/SQL     few-shot prompting
                                      pairs          Claude Opus 4.8
```

**Data flow:**
1. `collect_nba_data.py` pulls Celtics 2023–24 data from `nba_api` and bulk-inserts into PostgreSQL via `psycopg2.extras.execute_values`.
2. `annotation/annotation_batch_class{1-8}_*.csv` hold the hand-annotated WOZ corpus — the source of truth for both few-shot examples and evaluation gold SQL.
3. `model/nl2sql.py` loads approved annotation pairs at init, selects 3 examples per query by keyword overlap, and calls Claude Opus 4.8 with the schema + examples injected into the prompt.
4. `model/evaluate.py` splits the corpus 80/20 (seed=42), runs inference on the test split, and compares results via execution against the live DB.

**`NL2SQL` inference pipeline** (`model/nl2sql.py`):
- `load_examples()` — reads all 8 annotation CSVs, keeps only `execution_pass=TRUE` pairs
- `select_examples()` — keyword-scores each query class and samples 3 from the best match; falls back to random cross-class sampling if pool is small
- `build_prompt()` — injects `DB_SCHEMA` (hardcoded in `nl2sql.py`), 3 examples, and a coreference block if `prior_sql` is provided
- `NL2SQL.predict()` — calls `claude-opus-4-8` with `thinking: {"type": "adaptive"}`; strips markdown fences from response

**Coreference resolution**: Turn 2+ utterances pass `prior_sql` to the prompt. The evaluator uses `is_coreference_turn()` (pronoun/starter heuristic) to decide when to supply the prior gold SQL as context.

**`results_match()` in `evaluate.py`**: Normalized comparison — case-insensitive, column-name-agnostic, row-order-independent, float-tolerant (2 decimal places). Includes a numeric-value fallback for row-vs-column transpositions (e.g., a 1-row 2-column pivot vs. a 2-row GROUP BY producing the same numbers).

## Database Schema

4 tables in `nba_spatial` PostgreSQL database. Schema defined in `schema.sql`.

```
players(player_id PK, name, team, position, height, weight, draft_year)
games(game_id PK, date, home_team, away_team, venue, score, season_type)
shot_charts(id, player_id FK, game_id FK, shot_type, x, y, distance,
            made_flag, defender, minutes_remaining, period_seconds_remaining, period)
play_by_play(id, event_id, game_id FK, event_type, game_clock, player_ids, lineups, running_score)
```

**Critical unit distinction** (the source of multiple bugs):
- `x`, `y` (LOC_X, LOC_Y) — **tenths of feet** (range: −250 to +250, 0 to 470)
- `distance` (SHOT_DISTANCE) — **whole feet** (range: 0 to ~76)
- Always use `distance > 22` (not `> 220`) for above-break 3-pointers

**Spatial zone canonical filters** (from `DB_SCHEMA` in `nl2sql.py`):
```sql
left_corner_3:   x <= -220 AND y <= 90
right_corner_3:  x >= 220 AND y <= 90
above_break_3:   y > 90 AND distance > 22
restricted_area: distance <= 4 OR (ABS(x) <= 80 AND y <= 190)
in_the_paint:    ABS(x) <= 80 AND y <= 190
mid_range:       distance BETWEEN 8 AND 22
```

**Other schema gotchas:**
- `season_type` values are `'Regular'` and `'Playoff'` (not `'Regular Season'`/`'Playoffs'`)
- `game_id` is a zero-padded 10-digit string: prefix `002` = Regular, `004` = Playoff
- `period_seconds_remaining` is time left in the period (0–59s component of MM:SS display), NOT shot-clock time. No shot-clock column exists in the dataset.
- Total seconds left in period = `minutes_remaining * 60 + period_seconds_remaining`
- `defender` is NULL for all rows — ShotChartDetail API does not provide it
- `made_flag`: 1 = made, 0 = missed; `shot_type`: `'2PT Field Goal'` or `'3PT Field Goal'`

## Annotation Corpus

8 CSV files in `annotation/`, one per query class. Columns include `utterance`, `gold_sql`, `execution_pass`, `notes`, `state_auditor`, `state`.

Only rows with `execution_pass=TRUE` are used for few-shot examples and evaluation. The one permanent `execution_pass=FALSE` row is a "contested shots" query — `defender` is NULL in the entire dataset.

## nba_api Quirks

- **Playoff shot charts**: `ShotChartDetail` with `game_id_nullable` silently returns 0 rows for playoff game IDs (`004xxxxxxx`). Fetch all playoff shots in a single call using `season_type_all_star='Playoffs'` with no `game_id_nullable`.
- **PlayByPlayV3** returns camelCase columns (`gameId`, `actionNumber`, `actionType`, `clock`, `personId`, `scoreHome`, `scoreAway`). All other nba_api endpoints use UPPERCASE.
- Season format must be the string `'2023-24'` (not integer `2023`).
- `players` table must contain all NBA players (from `nba_api.stats.static.players.get_players()`), not just the Celtics roster — shot charts include opposing players, which causes FK violations if only Celtics players are loaded.

## Environment

Required environment variables (`.env`):
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=nba_spatial
DB_USER=<postgres username>
DB_PASSWORD=
ANTHROPIC_API_KEY=<key>
```

`DB_USER` defaults differ between scripts: `collect_nba_data.py` defaults to `postgres`; `evaluate.py` defaults to `rosalinatorres`.
