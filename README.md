# NBA CoSQL Spatial Pipeline

**IE7500 Natural Language Processing | Northeastern EDGE | Summer 2026**  
**Team: Rosalina Torres, Craig Habel, Sean Lynch**

> Conversational Text-to-SQL (CoSQL) pipeline over NBA spatial shot-chart data with a full WOZ annotation layer.

---

## Overview

This project builds a conversational NL→SQL system over NBA player tracking data. Users ask basketball questions in natural language across multi-turn dialogues; the system resolves coreference across turns and maps each utterance to an executable SQL query against a PostgreSQL database (`nba_spatial`).

**Data:** Boston Celtics 2023–24 season — shot charts, play-by-play, game logs  
**Annotation:** 139 WOZ NL/SQL pairs across 8 query classes, execution-verified against a live database  
**Pipeline:** `nba_api` → PostgreSQL → annotated training corpus

---

## Repository Structure

```
nba-cosql-spatial-pipeline/
├── schema.sql                    # PostgreSQL schema (4 tables, FK constraints)
├── collect_nba_data.py           # nba_api data collection script
├── load_csvs_to_db.py            # CSV → PostgreSQL bulk loader
├── kappa_report.py               # Inter-annotator agreement report
├── cosql_annotation_review.html  # Standalone annotation review tool (open in browser)
│
├── annotation/                   # 8 query class CSVs — 139 NL/SQL pairs
├── docs/
│   ├── BUG_REPORT.md             # 13 bugs documented with root causes + fixes
│   ├── ANNOTATION_SHEET_SETUP.md # WOZ annotation protocol
│   ├── NBA_API_REFERENCE.md      # nba_api v1.11.4 field reference
│   └── query_classes_and_clarify_templates.md
│
├── sql_training_full.csv         # Flat training corpus (all 139 pairs)
└── woz_annotation_template.csv   # Blank WOZ template
```

---

## Database

```sql
players     (player_id, name, team, position, height, weight, draft_year)
games       (game_id, date, home_team, away_team, venue, score, season_type)
shot_charts (id, player_id, game_id, shot_type, x, y, distance, made_flag,
             defender, minutes_remaining, period_seconds_remaining, period)
play_by_play(id, event_id, game_id, event_type, game_clock, player_ids,
             lineups, running_score)
```

| Table | Rows |
|---|---|
| players | 4,536 |
| games | 106 (82 Regular + 19 Playoff + 5 Preseason) |
| shot_charts | 8,989 (7,396 Regular + 1,593 Playoff) |
| play_by_play | 47,132 |

---

## Annotation

139 NL/SQL pairs across 8 query classes — all execution-verified against the live `nba_spatial` database.

| Class | Pairs |
|---|---|
| Spatial Zone | 18 |
| Temporal Scope | 18 |
| Player/Entity | 18 |
| Simple Aggregation | 18 |
| Comparative Aggregation | 18 |
| Multi-Turn Coreference | 16 |
| Game/Matchup Context | 18 |
| Shot Characteristics | 15 |

**Execution accuracy:** 138/139 (99.3%)  
**Cross-rater agreement:** 68/69 (98.6%)

---

## Setup

```bash
# Install dependencies
pip install nba-api psycopg2-binary python-dotenv pandas

# Create database and schema
createdb nba_spatial
psql nba_spatial < schema.sql

# Configure environment
cp .env.example .env

# Collect data
python collect_nba_data.py

# Run IAA report
python kappa_report.py
```

---

## Annotation Review Tool

Open `cosql_annotation_review.html` in any browser — no server required. Reviewers can browse all 139 pairs, leave verdicts, add notes, and export results as CSV.
