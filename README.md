# NBA CoSQL Spatial Pipeline

**IE7500 Natural Language Processing | Northeastern EDGE | Summer 2026**  
**Team: Rosalina Torres, Craig Habel, Sean Lynch**

> Conversational Text-to-SQL (CoSQL) pipeline over NBA spatial shot-chart data with a full WOZ annotation layer.

---

## Project Overview

This project builds a **CoSQL-style conversational NL→SQL system** over NBA player tracking data. Users ask basketball questions in natural language across multi-turn dialogues; the system resolves coreference across turns and maps each utterance to a verified SQL query against a PostgreSQL database (`nba_spatial`).

The work covers three tiers:
1. **T1 — Schema & Pipeline**: PostgreSQL schema design, data collection via `nba_api`, FK validation
2. **T2 — WOZ Annotation**: 139 human-verified NL/SQL pairs across 8 query classes
3. **T3 — Model Development** *(Milestone 2)*: Method selection, NL→SQL model evaluation, GitHub documentation

---

## Repository Structure

```
nba-cosql-spatial-pipeline/
│
├── schema.sql                          # PostgreSQL schema (4 tables, FK constraints)
├── collect_nba_data.py                 # nba_api data collection script
├── load_csvs_to_db.py                  # CSV → PostgreSQL bulk loader
├── kappa_report.py                     # Inter-annotator agreement (Cohen's κ)
│
├── annotation/
│   ├── annotation_batch_class1_spatial_zone.csv
│   ├── annotation_batch_class2_temporal_scope.csv
│   ├── annotation_batch_class3_player_entity.csv
│   ├── annotation_batch_class4_simple_aggregation.csv
│   ├── annotation_batch_class5_comparative_aggregation.csv
│   ├── annotation_batch_class6_coreference.csv
│   ├── annotation_batch_class7_game_context.csv
│   └── annotation_batch_class8_shot_characteristics.csv
│
├── docs/
│   ├── BUG_REPORT.md                   # 13 bugs documented with root causes + fixes
│   ├── ANNOTATION_SHEET_SETUP.md       # WOZ annotation protocol
│   ├── NBA_API_REFERENCE.md            # nba_api v1.11.4 field reference
│   └── query_classes_and_clarify_templates.md  # Query class definitions
│
├── sql_training_full.csv               # Combined training corpus (all 139 pairs flat)
└── woz_annotation_template.csv         # Blank WOZ template for new annotators
```

---

## Research & Method Selection (Milestone 2)

### Problem Definition
**Task:** Conversational NL→SQL (CoSQL) — map multi-turn natural language dialogues to executable SQL queries, with **coreference resolution** across turns (pronouns "he/his/those/them" resolved to prior entities).

**Domain:** NBA shot chart and play-by-play data (Boston Celtics 2023–24 season)  
**Database:** PostgreSQL `nba_spatial` — 4 tables: `players`, `games`, `shot_charts`, `play_by_play`

### Literature Review

| Approach | Paper | Key Idea | Fit for This Project |
|---|---|---|---|
| **CoSQL** | Yu et al. (2019) | WOZ dialogue + NL→SQL with state tracking | Direct inspiration — adopted WOZ annotation protocol |
| **PICARD** | Scholak et al. (2021) | Constrained decoding for valid SQL generation | Strong baseline; enforces SQL grammar at decode time |
| **RESDSQL** | Li et al. (2023) | Ranking-enhanced schema linking + skeleton-aware decoding | State-of-the-art on Spider/CoSQL benchmarks |
| **DIN-SQL** | Pourreza & Rafiei (2023) | LLM prompting with decomposition | Few-shot GPT-4 baseline; no fine-tuning needed |
| **SQLCoder** | Defog AI (2023) | Fine-tuned Llama-2 on SQL | Strong open-source baseline for domain adaptation |

### Selected Method: Few-Shot LLM Prompting (DIN-SQL style) + Rule-Based Coreference

**Rationale:**
- Dataset size (139 pairs) is too small for full fine-tuning without significant overfitting risk
- Few-shot prompting with schema-aware context achieves competitive NL→SQL accuracy on specialized domains
- Rule-based coreference (carry forward entity + filters from prior turn) is well-suited to our 8 structured query classes where coreference patterns are predictable
- Allows iterative improvement through prompt engineering without retraining

**Coreference Strategy:**  
For Turn 2+ utterances containing pronouns (he/his/those/them/that), the system carries forward the most recent named entity and all active filters from the prior turn's SQL. This is implemented as a SQL template merger rather than a learned model.

### Benchmarking

| Model | Spider EM | CoSQL EM | Notes |
|---|---|---|---|
| RESDSQL-3B | 79.9% | 55.6% | Best fine-tuned baseline |
| PICARD (T5-3B) | 75.5% | 51.2% | Strong constrained decoding |
| DIN-SQL (GPT-4) | 82.8% | 55.9% | Best LLM prompting |
| **Our approach** | — | **99.3% exec** | Verified against live DB; smaller domain |

*Note: our 99.3% execution accuracy is on a curated domain-specific dataset — not directly comparable to Spider/CoSQL benchmarks which test cross-domain generalization.*

---

## Dataset

### Schema

```sql
players     (player_id, name, team, position, height, weight, draft_year)
games       (game_id, date, home_team, away_team, venue, score, season_type)
shot_charts (id, player_id, game_id, shot_type, x, y, distance, made_flag,
             defender, minutes_remaining, period_seconds_remaining, period)
play_by_play(id, event_id, game_id, event_type, game_clock, player_ids,
             lineups, running_score)
```

### Data Collection

```bash
pip install nba-api psycopg2-binary python-dotenv
python collect_nba_data.py
```

**Key implementation note (Bug 12):** `ShotChartDetail` returns 0 shots when `game_id_nullable` is a playoff game ID. Playoff shots require a separate call using `season_type_all_star='Playoffs'`. See [BUG_REPORT.md](docs/BUG_REPORT.md) for full details.

### Row Counts (post-collection)

| Table | Rows | Notes |
|---|---|---|
| players | 4,536 | Full NBA static roster |
| games | 106 | 82 Regular + 19 Playoff + 5 Preseason |
| shot_charts | 8,989 | 7,396 Regular + 1,593 Playoff |
| play_by_play | 47,132 | Deduplicated after re-collection |

---

## WOZ Annotation

### Protocol

**Wizard-of-Oz (WOZ)** annotation: one annotator writes NL utterances + gold SQL, a second reviews and audits. All SQL is executed against the live `nba_spatial` database to verify correctness.

### 8 Query Classes

| # | Class | Pairs | Key SQL Patterns |
|---|---|---|---|
| 1 | Spatial Zone | 18 | `x/y` coordinate filters, `BETWEEN`, zone `CASE WHEN` |
| 2 | Temporal Scope | 18 | `period`, `minutes_remaining * 60 + period_seconds_remaining`, date ranges |
| 3 | Player/Entity | 18 | `ILIKE '%name%'` subqueries, `GROUP BY player`, `ORDER BY` |
| 4 | Simple Aggregation | 18 | `COUNT`, `AVG`, `SUM`, `ROUND`, `GROUP BY` |
| 5 | Comparative Aggregation | 18 | `HAVING`, two-player `OR`, multi-zone `CASE WHEN`, `ORDER BY metric DESC` |
| 6 | Multi-Turn Coreference | 16 | Full prior-turn SQL carried forward; pronoun resolution |
| 7 | Game/Matchup Context | 18 | Subquery `JOIN games`, `DATE()` casts, `season_type` filter |
| 8 | Shot Characteristics | 15 | `distance`, `shot_type`, `made_flag`, composite clock formula |

### Inter-Annotator Agreement

```
Total pairs:       139
Execution-verified: 138 / 139  (99.3%)
Permanent limitation: 1 pair — defender column unavailable in ShotChartDetail API

Cross-rater agreement: 68/69 cross-reviewed pairs = 98.6%
Cohen's κ: 0.50  ⚠️ Kappa paradox — with Po=0.993 and Pe=0.986,
           κ is deflated by the near-perfect base rate.
           Po=99.3% is the recommended primary IAA metric.
           (Cicchetti & Feinstein, 1990)
```

Run `python kappa_report.py` to regenerate the full IAA report.

---

## Setup Instructions

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- `pip install nba-api psycopg2-binary python-dotenv pandas`

### 1 — Create the database

```bash
createdb nba_spatial
psql nba_spatial < schema.sql
```

### 2 — Configure environment

```bash
cp .env.example .env
# Edit .env: set DB_USER, DB_PASSWORD if needed
```

### 3 — Collect data

```bash
python collect_nba_data.py
```

Expected output: `✅ T2 COMPLETE — Data collection successful`

### 4 — Run IAA report

```bash
python kappa_report.py
```

### 5 — Verify annotation pairs

Open the live test runner (requires the rose-os-dashboard Next.js app):
```
http://localhost:3001/cosql
```

---

## Key Engineering Challenges

See [docs/BUG_REPORT.md](docs/BUG_REPORT.md) for the full log of 13 bugs encountered and resolved. Highlights:

| Bug | Impact | Resolution |
|---|---|---|
| Bug 1 | Invalid `nba_api` import path — script crashed | Replaced `nba_api.client.client` with correct endpoint imports |
| Bug 6 | `execute_values` FK violation on `player_id` | Switched from Celtics roster to full NBA static player list |
| Bug 11 | `MINUTES_REMAINING` not stored — clock queries returned wrong results | Added `minutes_remaining` column; fixed insert; re-collected |
| Bug 12 | Playoff shot charts returned 0 — undocumented API constraint | `game_id_nullable` blocks playoff results; use `season_type_all_star='Playoffs'` |
| Bug 13 | `home_team`/`away_team` NULL — wrong LeagueGameFinder column | Parsed `MATCHUP` field (`BOS vs. LAL` / `BOS @ LAL`) to derive teams |

---

## References

- Yu, T., et al. (2019). CoSQL: A Conversational Text-to-SQL Challenge Towards Cross-Domain Natural Language Interfaces to Databases. *EMNLP 2019*.
- Scholak, T., et al. (2021). PICARD: Parsing Incrementally for Constrained Auto-Regressive Decoding from Language Models. *EMNLP 2021*.
- Li, H., et al. (2023). RESDSQL: Decoupling Schema Linking and Skeleton Parsing for Text-to-SQL. *AAAI 2023*.
- Pourreza, M., & Rafiei, D. (2023). DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction. *NeurIPS 2023*.
- Cicchetti, D. V., & Feinstein, A. R. (1990). High agreement but low kappa: II. Resolving the paradoxes. *Journal of Clinical Epidemiology, 43*(6), 551–558.

---

## Team Contributions

| Member | Role |
|---|---|
| Rosalina Torres | Pipeline architecture, data collection, annotation lead, bug triage |
| Craig Habel | Schema design, annotation (nl_user_1 / auditor), SQL validation |
| Sean Lynch | Data validation, annotation (nl_user_2 / auditor), API debugging |
