# NBA CoSQL Spatial Pipeline

**IE7500 Natural Language Processing | Northeastern University COE | Summer 2026**  
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
│   ├── EVALUATION_RESULTS.md     # Full iteration history: 42.9% → 67.9% → 85.7%
│   ├── BUG_REPORT.md             # 13 bugs documented with root causes + fixes
│   ├── ANNOTATION_SHEET_SETUP.md # WOZ annotation protocol
│   ├── NBA_API_REFERENCE.md      # nba_api v1.11.4 field reference
│   └── query_classes_and_clarify_templates.md
│
├── model/
│   ├── nl2sql.py                 # Few-shot NL→SQL inference (DIN-SQL style, Claude API)
│   └── evaluate.py               # Execution accuracy evaluation on held-out test split
│
├── sql_training_full.csv         # Flat training corpus (all 139 pairs)
├── requirements.txt              # Pinned Python dependencies
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

## Model

Few-shot NL→SQL inference using Claude Opus 4.8 (DIN-SQL style):

```python
from model.nl2sql import NL2SQL

model = NL2SQL()

# Single turn
sql = model.predict("How many 3-pointers did Tatum make from the left corner?")

# Multi-turn coreference
results = model.predict_conversation([
    "How many shots did Jaylen Brown attempt in Q4?",
    "What about only his made shots?",
    "And just from the restricted area?",
])
```

Evaluate execution accuracy on a held-out test split:

```bash
python model/evaluate.py --split 0.2 --seed 42
```

---

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

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
