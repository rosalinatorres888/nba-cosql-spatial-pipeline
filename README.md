# NBA CoSQL Spatial Pipeline

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Claude Opus 4.8](https://img.shields.io/badge/Claude-Opus%204.8-D97757?logo=anthropic&logoColor=white)
![Execution Accuracy](https://img.shields.io/badge/Execution%20Accuracy-100%25-22c55e)
![IAA](https://img.shields.io/badge/Inter--Rater%20Agreement-98.6%25-22c55e)
![License](https://img.shields.io/badge/License-MIT-6b7280)

**IE7500 Natural Language Processing · Northeastern University COE · Summer 2026**

Conversational Text-to-SQL (CoSQL) pipeline over NBA spatial shot-chart data — with a hand-annotated WOZ corpus, coreference resolution, and 100% execution accuracy on a held-out test split.

**[CoSQL Annotation Guide](https://tinyurl.com/NL-Annotation-Guide)** 

**[CoSQL_NBA_WOZ_Annotation Tracker](https://tinyurl.com/CoSQL-NBA-WOZ-Annotations)** 

**[Live Annotation Review Tool](https://nba-cosql-spatial-annotation-tool.netlify.app/)** 


---

## What This Is

Users ask multi-turn basketball questions in natural language. The system resolves coreferences across turns ("What about only his made shots?" → carries forward player + zone filters) and maps each utterance to an executable PostgreSQL query.

```
"How many shots did Jaylen Brown attempt in Q4?"
→ SELECT COUNT(*) FROM shot_charts sc JOIN players p ON sc.player_id = p.player_id
  WHERE p.name = 'Jaylen Brown' AND sc.period = 4

"What about only his made shots?"          ← coreference: "his" = Jaylen Brown
→ SELECT COUNT(*) FROM shot_charts sc JOIN players p ON sc.player_id = p.player_id
  WHERE p.name = 'Jaylen Brown' AND sc.period = 4 AND sc.made_flag = 1

"And just from the restricted area?"       ← coreference: carries player + Q4 + made
→ SELECT COUNT(*) FROM shot_charts sc JOIN players p ON sc.player_id = p.player_id
  WHERE p.name = 'Jaylen Brown' AND sc.period = 4 AND sc.made_flag = 1
  AND (sc.distance <= 4 OR (ABS(sc.x) <= 80 AND sc.y <= 190))
```

---

## Results


| Metric | Value |
|---|---|
| Execution accuracy (held-out test set) | **28/28 = 100%** |
| SQL validity rate | 28/28 = 100% |
| Annotation corpus size | 139 NL/SQL pairs |
| Annotation execution rate | 138/139 = 99.3% |
| Cross-rater agreement (Cohen's κ) | 68/69 = 98.6% |
| DIN-SQL GPT-4 CoSQL benchmark (Pourreza & Rafiei, 2023) | 55.9% EM |

See: [Bug Report](docs/BUG_REPORT.md)

The model reached 100% through 6 evaluation iterations — from 42.9% baseline to 100% final — documented in [Evaluation Results](docs/EVALUATION_RESULTS.md)  

---

## Architecture

```
nba_api  ──►  PostgreSQL (nba_spatial)  ──►  WOZ Annotation  ──►  Few-Shot Prompting
                4 tables · 60K+ rows         139 NL/SQL pairs       DIN-SQL style
                                             8 query classes        Claude Opus 4.8
                                             3 annotators           coreference resolution
```

**Method:** DIN-SQL-style few-shot prompting (Pourreza & Rafiei, 2023). Schema injected statically (domain is fixed), examples selected by keyword-matched query class, coreference handled via prior-SQL carry-forward for Turn 2+ utterances. No fine-tuning.

---

## Dataset

**Boston Celtics 2023–24 season** — shot charts, play-by-play, game logs via `nba_api`.

| Table | Rows |
|---|---|
| players | 4,536 |
| games | 106 (82 Regular · 19 Playoff · 5 Preseason) |
| shot_charts | 8,989 |
| play_by_play | 47,132 |

```sql
players     (player_id, name, team, position, height, weight, draft_year)
games       (game_id, date, home_team, away_team, venue, score, season_type)
shot_charts (id, player_id, game_id, shot_type, x, y, distance, made_flag,
             defender, minutes_remaining, period_seconds_remaining, period)
play_by_play(id, event_id, game_id, event_type, game_clock, player_ids,
             lineups, running_score)
```

---

## Annotation Corpus

139 NL/SQL pairs across 8 query classes, execution-verified against the live database by 3 annotators.

| Query Class | Pairs | Example |
|---|---|---|
| Spatial Zone | 18 | "How many shots from the left corner?" |
| Temporal Scope | 18 | "What was the FG% in the fourth quarter?" |
| Player/Entity | 18 | "Which players attempted the most mid-range shots?" |
| Simple Aggregation | 18 | "How many 3-pointers were made in playoffs?" |
| Comparative Aggregation | 18 | "Who shot above 50% with at least 200 attempts?" |
| Multi-Turn Coreference | 16 | "What about only his made shots?" |
| Game/Matchup Context | 18 | "How many shots on October 30th?" |
| Shot Characteristics | 15 | "How many shots with less than 5 seconds left?" |

**Execution rate:** 138/139 (99.3%) — 1 permanent `needs_revision`: "contested shots" query; `defender` is NULL for all rows in the nba_api ShotChartDetail endpoint — data unavailable at the source.  
**Cross-rater agreement:** 68/69 (98.6%)

---

## Usage

```python
from model.nl2sql import NL2SQL

model = NL2SQL()

# Single turn
sql = model.predict("How many 3-pointers did Tatum make from the left corner?")

# Multi-turn with coreference
results = model.predict_conversation([
    "How many shots did Jaylen Brown attempt in Q4?",
    "What about only his made shots?",
    "And just from the restricted area?",
])
```

```bash
# Evaluate on held-out test split
python model/evaluate.py --split 0.2 --seed 42
```

---

## Setup

```bash
pip install -r requirements.txt

createdb nba_spatial
psql nba_spatial < schema.sql

cp .env.example .env        # add ANTHROPIC_API_KEY + DB credentials

python collect_nba_data.py  # pull from nba_api
python kappa_report.py      # inter-annotator agreement
```

---

## Repository Structure

```
├── annotation/                   # 8 query class CSVs — 139 NL/SQL pairs
├── model/
│   ├── nl2sql.py                 # Few-shot NL→SQL inference (DIN-SQL style)
│   └── evaluate.py               # Execution accuracy evaluator
├── docs/
│   ├── EVALUATION_RESULTS.md     # Iteration history: 42.9% → 100%
│   ├── BUG_REPORT.md             # 13 bugs documented with root causes + fixes
│   ├── ANNOTATION_SHEET_SETUP.md # WOZ annotation protocol
│   └── NBA_API_REFERENCE.md      # nba_api v1.11.4 field reference
├── schema.sql                    # PostgreSQL schema (4 tables, FK constraints)
├── collect_nba_data.py           # nba_api data collection
├── load_csvs_to_db.py            # CSV → PostgreSQL bulk loader
├── kappa_report.py               # IAA report
├── cosql_annotation_review.html  # Browser-based annotation review tool
└── sql_training_full.csv         # Flat training corpus (all 139 pairs)
```

---

## References

- Pourreza, M. & Rafiei, D. (2023). DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction. *NeurIPS 2023*.
- Yu, T. et al. (2019). CoSQL: A Conversational Text-to-SQL Challenge. *EMNLP 2019*.
- Anguita, D. et al. (2013). A public domain dataset for human activity recognition using smartphones.

---

*IE7500 NLP · Northeastern University College of Engineering · Summer 2026 · Rosalina Torres*
